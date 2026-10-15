export { default as ApiService } from './api.service';
export { default as AuthService } from './auth.service';
export { default as LocationService } from './location.service';
export { default as NotificationService } from './notification.service';
export { crimeService } from './crime.service';
export type { CrimeAnalysisResult } from './crime.service';
// `speechService` was removed in B8 along with `hooks/useVoiceRecorder`.
// Both existed only to record a clip and upload it to /ai/speech-to-text so the
// hot-words screen could fill in a text field. Hot-word dictation is now
// on-device (`features/voice/dictate.ts`), which left them with no callers --
// and an unused path that uploads a recording of someone's voice is not the
// kind of dead code to leave lying about. The backend's /ai/speech-to-text was
// deleted on 2026-10-15 — that closed defect 2, and the reasoning was the same
// one written here: it had no caller, and it raised NameError if it ever got one.
export { riskService } from './risk.service';
export type { RiskFlagsResult, MapRegion } from './risk.service';
// Defect 16. `routeService` was the one service imported from its file while
// every sibling came from here, so a reader could not tell from the barrel that
// routing had a service at all.
//
// `Location` is deliberately NOT re-exported: route.service.ts declares one, so
// does location.service.ts's domain, and `Location` is a global in the DOM lib.
// A barrel is the worst place to make a name that generic ambiguous.
export { routeService } from './route.service';
export type { RouteRequest, RouteResponse } from './route.service';
