import logging
import math
import httpx
from typing import List, Tuple, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.crime import CrimeReport
from app.schemas.route import RouteRequest, RouteResponse, RouteSegment, Location

import json
import os

logger = logging.getLogger(__name__)

class RouteService:
    def __init__(self):
        self.risk_model = {}
        self._load_risk_model()

    def _load_risk_model(self):
        try:
            # Path to backend/scripts/crime_risk_model.json
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            model_path = os.path.join(base_dir, "scripts", "crime_risk_model.json")
            
            if os.path.exists(model_path):
                with open(model_path, "r") as f:
                    self.risk_model = json.load(f)
                logger.info("✅ Crime Risk Model loaded successfully")
            else:
                logger.warning(f"⚠️ Crime Risk Model not found at {model_path}")
        except Exception as e:
            logger.error(f"Failed to load Crime Risk Model: {e}")

    def _haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance between two points in km"""
        R = 6371  # Earth radius in km
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat/2) * math.sin(dlat/2) + \
            math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * \
            math.sin(dlon/2) * math.sin(dlon/2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        return R * c
        
    def _get_regional_risk(self, lat: float, lon: float) -> float:
        """Get normalized risk score based on regional model (0-100)"""
        max_risk = 0.0
        
        for unit, data in self.risk_model.items():
            center = data.get("location", {})
            c_lat = center.get("lat")
            c_lon = center.get("lon")
            radius = center.get("radius_km", 10)
            
            if c_lat and c_lon:
                dist = self._haversine_distance(lat, lon, c_lat, c_lon)
                if dist <= radius:
                    # Point is within this high-risk zone
                    # We take the max risk if overlapping zones
                    risk = data.get("normalized_risk", 0.0)
                    if risk > max_risk:
                        max_risk = risk
                        
        return max_risk

    def _generate_path(self, start: Location, end: Location, num_points: int = 10, curve_factor: float = 0.0) -> List[Tuple[float, float]]:
        """
        Generate a simulated path if OSRM fails.
        """
        path = []
        for i in range(num_points + 1):
            t = i / num_points
            lat = start.latitude + t * (end.latitude - start.latitude)
            lng = start.longitude + t * (end.longitude - start.longitude)
            if curve_factor != 0:
                deviation = math.sin(t * math.pi) * curve_factor
                lat += deviation * 0.01
                lng += deviation * 0.01
            path.append((lat, lng))
        return path

    async def _fetch_osrm_routes(self, start: Location, end: Location) -> List[dict]:
        """Fetch real routes from OSRM"""
        # OSRM demo server (use with care, rate/reliability not guaranteed for prod)
        url = f"http://router.project-osrm.org/route/v1/driving/{start.longitude},{start.latitude};{end.longitude},{end.latitude}"
        params = {
            "overview": "full",
            "geometries": "geojson",
            "alternatives": "true"
        }
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params, timeout=5.0)
                if response.status_code == 200:
                    data = response.json()
                    if data.get("code") == "Ok":
                        return data.get("routes", [])
        except Exception as e:
            logger.error(f"OSRM Fetch Error: {e}")
        return []

    async def _calculate_path_risk(self, path: List[Tuple[float, float]], db: AsyncSession) -> Tuple[float, List[Location]]:
        """
        Calculate risk score for a path based on nearby crimes AND regional model.
        Returns (risk_score, hotspots_list)
        """
        local_incident_risk = 0.0
        hotspots = []
        
        # 1. Regional Risk Calculation (Base Level)
        # Sample points along path to determine max regional risk
        # We check every 10th point to save compute
        regional_risks = []
        sample_step = max(1, len(path) // 20)
        for i in range(0, len(path), sample_step):
            p = path[i]
            regional_risks.append(self._get_regional_risk(p[0], p[1]))
            
        avg_regional_risk = sum(regional_risks) / len(regional_risks) if regional_risks else 0.0
        
        # 2. Local Incident Risk Calculation (Specific Crimes)
        # Optimization: Query all active crimes and filter in Python for stability
        query = select(CrimeReport).where(CrimeReport.status.in_(['verified', 'pending', 'investigating']))
        result = await db.execute(query)
        all_crimes = result.scalars().all()
        
        # Calculate bounding box for the path
        lats = [p[0] for p in path]
        lngs = [p[1] for p in path]
        if not lats or not lngs:
             return 100.0, []
             
        padding = 0.05
        min_lat, max_lat = min(lats) - padding, max(lats) + padding
        min_lng, max_lng = min(lngs) - padding, max(lngs) + padding
        
        # Pre-filter crimes in bounding box
        crimes = []
        for crime in all_crimes:
            try:
                c_lat = float(crime.latitude)
                c_lng = float(crime.longitude)
                if min_lat <= c_lat <= max_lat and min_lng <= c_lng <= max_lng:
                    crimes.append(crime)
            except (ValueError, TypeError):
                continue
        
        processed_crimes = set()
        
        for lat, lng in path:
            for crime in crimes:
                try:
                    c_lat = float(crime.latitude)
                    c_lng = float(crime.longitude)
                except: continue

                # Check if crime is within 500m (0.5km)
                if abs(c_lat - lat) < 0.0045 and abs(c_lng - lng) < 0.0045:
                    if crime.id not in processed_crimes:
                        weight = 10.0
                        cat = str(crime.category).lower()
                        if 'theft' in cat: weight = 5.0
                        elif 'assault' in cat: weight = 20.0
                        elif 'murder' in cat: weight = 50.0
                        elif 'robbery' in cat: weight = 30.0
                        
                        local_incident_risk += weight
                        processed_crimes.add(crime.id)
                        hotspots.append(Location(latitude=c_lat, longitude=c_lng))
        
        # Combine Risks
        # Regional Risk (0-100) contributes 30% to danger
        # Local Incident Risk (unbounded, usually 0-200) contributes 70%
        # We cap local risk contribution at 100 for normalization
        
        capped_local_risk = min(100.0, local_incident_risk)
        
        total_risk_score = (avg_regional_risk * 0.3) + (capped_local_risk * 0.7)
        
        # Safety Score is inverse of Risk
        safety_score = max(0.0, 100.0 - total_risk_score)
        
        return safety_score, hotspots

    async def calculate_routes(self, request: RouteRequest, db: AsyncSession) -> List[RouteResponse]:
        """
        Generate multiple routes and rank them by safety/distance.
        Uses OSRM for real paths, falls back to simulation if needed.
        """
        routes = []
        
        # Helper to build RouteResponse
        def build_response(rid, points, dist_km, safety, hotspots):
            segments = []
            for pt in points:
                segments.append(RouteSegment(latitude=pt[0], longitude=pt[1], crime_score=(100-safety)/10))
            
            # Simple composite: safety is 70% weight, distance is 30%
            dist_score = max(0.0, 100.0 - (dist_km * 2.0))
            composite = (safety * 0.7) + (dist_score * 0.3)
            
            return RouteResponse(
                route_id=rid,
                path=segments,
                distance_km=round(dist_km, 2),
                duration_minutes=int(dist_km * 60 / 30), # default 30km/h
                safety_score=round(safety, 1),
                composite_score=round(composite, 1),
                crime_hotspots=hotspots
            )

        # 1. Try OSRM
        osrm_routes = await self._fetch_osrm_routes(request.source, request.destination)
        
        if osrm_routes:
            for i, r in enumerate(osrm_routes):
                # Extract path (flip [lon, lat] to [lat, lon])
                coordinates = r['geometry']['coordinates']
                path = [(c[1], c[0]) for c in coordinates]
                
                # Distance
                dist_km = r['legs'][0]['distance'] / 1000.0
                
                # Calculate Safety
                safety, hotspots = await self._calculate_path_risk(path, db)
                
                routes.append(build_response(f"route_osrm_{i}", path, dist_km, safety, hotspots))
        
        # 2. Fallback if OSRM failed (empty list)
        if not routes:
            logger.warning("OSRM failed or returned no routes, using simulation.")
            s_lat, s_lng = request.source.latitude, request.source.longitude
            d_lat, d_lng = request.destination.latitude, request.destination.longitude
            base_distance = self._haversine_distance(s_lat, s_lng, d_lat, d_lng)
            
            path1 = self._generate_path(request.source, request.destination, num_points=20, curve_factor=0.0)
            safety1, hotspots1 = await self._calculate_path_risk(path1, db)
            routes.append(build_response("route_sim_1", path1, base_distance, safety1, hotspots1))
            
            path2 = self._generate_path(request.source, request.destination, num_points=25, curve_factor=1.0)
            safety2, hotspots2 = await self._calculate_path_risk(path2, db)
            routes.append(build_response("route_sim_2", path2, base_distance * 1.2, safety2, hotspots2))

        # Sort by composite score descending (Safest & Shortest combined, heavy safety weight)
        routes.sort(key=lambda x: x.composite_score, reverse=True)
        
        return routes

route_service = RouteService()
