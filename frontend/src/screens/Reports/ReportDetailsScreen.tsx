import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
  Alert,
} from 'react-native';
import { Ionicons, MaterialCommunityIcons } from '@expo/vector-icons';
import { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { RouteProp } from '@react-navigation/native';
import { ReportsStackParamList } from '../../types';
import { colors, spacing, borderRadius, fontSize } from '../../theme';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import MapView, { Marker, PROVIDER_GOOGLE } from '../../components/MapComponent';
import { crimeService } from '../../services/crime.service';

type ReportDetailsScreenNavigationProp = NativeStackNavigationProp<
  ReportsStackParamList,
  'ReportDetails'
>;

type ReportDetailsScreenRouteProp = RouteProp<
  ReportsStackParamList,
  'ReportDetails'
>;

interface Props {
  navigation: ReportDetailsScreenNavigationProp;
  route: ReportDetailsScreenRouteProp;
}

const ReportDetailsScreen: React.FC<Props> = ({ navigation, route }) => {
  const insets = useSafeAreaInsets();
  const { reportId } = route.params;
  const [report, setReport] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchReportDetails();
  }, [reportId]);

  const fetchReportDetails = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await crimeService.getReportById(reportId);
      setReport(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load report details');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = () => {
    Alert.alert(
      'Delete Report',
      'Are you sure you want to delete this report? This action cannot be undone.',
      [
        {
          text: 'Cancel',
          style: 'cancel',
        },
        {
          text: 'Delete',
          style: 'destructive',
          onPress: async () => {
            try {
              await crimeService.deleteReport(reportId);
              Alert.alert('Success', 'Report deleted successfully');
              navigation.goBack();
            } catch (err: any) {
              Alert.alert('Error', err.message || 'Failed to delete report');
            }
          },
        },
      ],
    );
  };

  const formatDate = (dateString: string) => {
    // Parse the ISO string without timezone conversion
    // Extract date and time components from the ISO string (format: 2024-12-10T14:30:00.000Z)
    const [datePart, timePart] = dateString.split('T');
    const [year, month, day] = datePart.split('-');
    const [time] = timePart.split('.');
    const [hours, minutes] = time.split(':');

    // Convert to 12-hour format
    const hour24 = parseInt(hours, 10);
    const hour12 = hour24 % 12 || 12;
    const ampm = hour24 >= 12 ? 'PM' : 'AM';

    // Format month name (full)
    const monthNames = [
      'January',
      'February',
      'March',
      'April',
      'May',
      'June',
      'July',
      'August',
      'September',
      'October',
      'November',
      'December',
    ];
    const monthName = monthNames[parseInt(month, 10) - 1];

    return `${monthName} ${parseInt(day, 10)}, ${year}, ${hour12}:${minutes} ${ampm}`;
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'verified':
        return colors.success;
      case 'investigating':
        return colors.info;
      case 'resolved':
        return colors.primary;
      default:
        return colors.warning;
    }
  };

  const getCategoryIcon = (category: string) => {
    const iconMap: any = {
      theft: 'bag-personal-outline',
      assault: 'hand-back-right-outline',
      harassment: 'account-alert-outline',
      vandalism: 'hammer-wrench',
      burglary: 'home-alert-outline',
      robbery: 'wallet-outline',
      fraud: 'credit-card-off-outline',
      other: 'alert-circle-outline',
    };
    return iconMap[category.toLowerCase()] || 'alert-circle-outline';
  };

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color={colors.primary} />
        <Text style={styles.loadingText}>Loading report details...</Text>
      </View>
    );
  }

  if (error || !report) {
    return (
      <View style={styles.errorContainer}>
        <MaterialCommunityIcons
          name="alert-circle-outline"
          size={64}
          color={colors.error}
        />
        <Text style={styles.errorText}>{error || 'Report not found'}</Text>
        <TouchableOpacity
          style={styles.retryButton}
          onPress={fetchReportDetails}
        >
          <Text style={styles.retryButtonText}>Retry</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={styles.backButton}
          onPress={() => navigation.goBack()}
        >
          <Text style={styles.backButtonText}>Go Back</Text>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      {/* Header */}
      <View style={[styles.header, { paddingTop: insets.top + spacing.md }]}>
        <TouchableOpacity
          style={styles.headerButton}
          onPress={() => navigation.goBack()}
        >
          <Ionicons name="arrow-back" size={24} color={colors.white} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Report Details</Text>
        <TouchableOpacity style={styles.headerButton} onPress={handleDelete}>
          <Ionicons name="trash-outline" size={24} color={colors.white} />
        </TouchableOpacity>
      </View>

      <ScrollView
        style={styles.content}
        contentContainerStyle={[
          styles.scrollContent,
          { paddingBottom: insets.bottom + spacing.lg },
        ]}
      >
        {/* Status Badge */}
        <View
          style={[
            styles.statusBadge,
            { backgroundColor: getStatusColor(report.status) },
          ]}
        >
          <Text style={styles.statusText}>
            {report.status.toUpperCase()}
            {report.verified && ' ✓'}
          </Text>
        </View>

        {/* Category Section */}
        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <MaterialCommunityIcons
              name={getCategoryIcon(report.category)}
              size={24}
              color={colors.primary}
            />
            <Text style={styles.sectionTitle}>Category</Text>
          </View>
          <Text style={styles.categoryValue}>
            {report.category.toUpperCase()}
          </Text>
        </View>

        {/* Title Section */}
        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <MaterialCommunityIcons
              name="text-box"
              size={24}
              color={colors.primary}
            />
            <Text style={styles.sectionTitle}>Title</Text>
          </View>
          <Text style={styles.contentText}>{report.title}</Text>
        </View>

        {/* Description Section */}
        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <MaterialCommunityIcons
              name="text"
              size={24}
              color={colors.primary}
            />
            <Text style={styles.sectionTitle}>Description</Text>
          </View>
          <Text style={styles.contentText}>{report.description}</Text>
        </View>

        {/* Date & Time Section */}
        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <Ionicons name="calendar" size={24} color={colors.primary} />
            <Text style={styles.sectionTitle}>Incident Date & Time</Text>
          </View>
          <Text style={styles.contentText}>
            {formatDate(report.incident_date_time)}
          </Text>
        </View>

        {/* Location Section */}
        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <Ionicons name="location" size={24} color={colors.primary} />
            <Text style={styles.sectionTitle}>Location</Text>
          </View>
          <Text style={styles.contentText}>
            {report.location_name || 'Location not specified'}
          </Text>
          <Text style={styles.coordinatesText}>
            {parseFloat(report.latitude).toFixed(6)},{' '}
            {parseFloat(report.longitude).toFixed(6)}
          </Text>
        </View>

        {/* Map */}
        <View style={styles.mapContainer}>
          <MapView
            provider={PROVIDER_GOOGLE}
            style={styles.map}
            initialRegion={{
              latitude: parseFloat(report.latitude),
              longitude: parseFloat(report.longitude),
              latitudeDelta: 0.01,
              longitudeDelta: 0.01,
            }}
            scrollEnabled={false}
            zoomEnabled={false}
          >
            <Marker
              coordinate={{
                latitude: parseFloat(report.latitude),
                longitude: parseFloat(report.longitude),
              }}
              title={report.category}
              description={report.location_name}
            />
          </MapView>
        </View>

        {/* Timestamps */}
        <View style={styles.timestampSection}>
          <View style={styles.timestampRow}>
            <MaterialCommunityIcons
              name="clock-outline"
              size={16}
              color={colors.textSecondary}
            />
            <Text style={styles.timestampLabel}>Reported: </Text>
            <Text style={styles.timestampValue}>
              {formatDate(report.created_at)}
            </Text>
          </View>
        </View>
      </ScrollView>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: colors.background,
  },
  loadingText: {
    marginTop: spacing.md,
    fontSize: fontSize.md,
    color: colors.textSecondary,
  },
  errorContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: colors.background,
    padding: spacing.xl,
  },
  errorText: {
    fontSize: fontSize.lg,
    color: colors.error,
    textAlign: 'center',
    marginTop: spacing.md,
    marginBottom: spacing.lg,
  },
  retryButton: {
    backgroundColor: colors.primary,
    paddingHorizontal: spacing.xl,
    paddingVertical: spacing.md,
    borderRadius: borderRadius.md,
    marginBottom: spacing.md,
  },
  retryButtonText: {
    color: colors.white,
    fontSize: fontSize.md,
    fontWeight: '600',
  },
  backButton: {
    backgroundColor: colors.gray300,
    paddingHorizontal: spacing.xl,
    paddingVertical: spacing.md,
    borderRadius: borderRadius.md,
  },
  backButtonText: {
    color: colors.textPrimary,
    fontSize: fontSize.md,
    fontWeight: '600',
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: spacing.lg,
    backgroundColor: colors.primary,
  },
  headerButton: {
    width: 40,
    height: 40,
    justifyContent: 'center',
    alignItems: 'center',
  },
  headerTitle: {
    fontSize: fontSize.xl,
    fontWeight: 'bold',
    color: colors.white,
  },
  content: {
    flex: 1,
  },
  scrollContent: {
    padding: spacing.lg,
  },
  statusBadge: {
    alignSelf: 'flex-start',
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: borderRadius.md,
    marginBottom: spacing.lg,
  },
  statusText: {
    color: colors.white,
    fontSize: fontSize.md,
    fontWeight: '700',
    letterSpacing: 1,
  },
  section: {
    backgroundColor: colors.surface,
    borderRadius: borderRadius.md,
    padding: spacing.md,
    marginBottom: spacing.md,
    elevation: 1,
    shadowColor: colors.shadow,
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.1,
    shadowRadius: 2,
  },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: spacing.sm,
  },
  sectionTitle: {
    fontSize: fontSize.lg,
    fontWeight: '600',
    color: colors.textPrimary,
    marginLeft: spacing.sm,
  },
  categoryValue: {
    fontSize: fontSize.lg,
    color: colors.primary,
    fontWeight: '600',
    textTransform: 'capitalize',
  },
  contentText: {
    fontSize: fontSize.md,
    color: colors.textPrimary,
    lineHeight: 22,
  },
  coordinatesText: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    marginTop: spacing.xs,
    fontFamily: 'monospace',
  },
  mapContainer: {
    height: 200,
    borderRadius: borderRadius.md,
    overflow: 'hidden',
    marginBottom: spacing.md,
    elevation: 2,
    shadowColor: colors.shadow,
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.15,
    shadowRadius: 3,
  },
  map: {
    flex: 1,
  },
  timestampSection: {
    backgroundColor: colors.surface,
    borderRadius: borderRadius.md,
    padding: spacing.md,
    elevation: 1,
    shadowColor: colors.shadow,
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.1,
    shadowRadius: 2,
  },
  timestampRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: spacing.xs,
  },
  timestampLabel: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    marginLeft: spacing.xs,
  },
  timestampValue: {
    fontSize: fontSize.sm,
    color: colors.textPrimary,
  },
});

export default ReportDetailsScreen;
