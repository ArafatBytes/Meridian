import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
  Alert,
  Image,
} from 'react-native';
import { Ionicons, MaterialCommunityIcons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { RouteProp } from '@react-navigation/native';
import { ReportsStackParamList } from '../../types';
import { useTheme } from '../../theme/ThemeProvider';
import { useStyles } from '../../theme/useStyles';
import type { Palette } from '../../theme/palette';
import { glassSurface, lift } from '../../theme/surfaces';
import { Aurora } from '../../components/motion';
import { fontFamily, radius, space, type } from '../../theme/type';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import MapView, { Marker, MAP_PROVIDER } from '../../components/MapComponent';
import { crimeService } from '../../services/crime.service';
import { reportStatusLabel } from '../../types/contracts/crime';

// @ts-ignore - generated types fight `style` in this RN version
const Grad = LinearGradient as any;

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
  const { t, g, mode } = useTheme();
  const styles = useStyles(makeStyles);
  const insets = useSafeAreaInsets();
  const { reportId } = route.params;
  const [report, setReport] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // D07: the evidence bucket is private, so the photo URL is signed on demand
  // and expires. Null means there is no photo, or it could not be signed.
  const [photoUrl, setPhotoUrl] = useState<string | null>(null);

  useEffect(() => {
    fetchReportDetails();
  }, [reportId]);

  const fetchReportDetails = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await crimeService.getReportById(reportId);
      setReport(data);
      if (data?.evidence_photo_path) {
        setPhotoUrl(await crimeService.getEvidencePhotoUrl(data.evidence_photo_path));
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load report details');
    } finally {
      setLoading(false);
    }
  };

  /**
   * Retract the report without destroying it. B13.
   *
   * The counterpart of corroboration, and the reason it is not just "delete": once a
   * report has contributed to a published cluster, deleting the row removes the audit
   * trail behind a claim that is still on other people's maps. Withdrawing leaves the
   * row, stops it counting on the corroboration agent's next run, and keeps the
   * cluster's provenance intact.
   *
   * Offered only on a report that is still on record. A withdrawn one has nothing to
   * withdraw, and `removed` is not the author's state to change.
   *
   * It goes through an RPC because the client deliberately has no UPDATE privilege on
   * `crime_reports.status` -- that column-level revoke is what closed the hole where
   * any account could self-award `verified = true` on its own row.
   */
  const handleWithdraw = () => {
    Alert.alert(
      'Withdraw Report',
      'This keeps your report but stops it counting toward what other people see on ' +
        'the map. You can still delete it afterwards.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Withdraw',
          onPress: async () => {
            try {
              const withdrawn = await crimeService.withdrawReport(reportId);
              if (!withdrawn) {
                // False is a legitimate answer, not an error: already withdrawn,
                // already removed, or not yours. Re-reading says which.
                Alert.alert('Already withdrawn', 'This report is no longer on record.');
              }
              await fetchReportDetails();
            } catch (err: any) {
              Alert.alert('Error', err.message || 'Failed to withdraw this report');
            }
          },
        },
      ],
    );
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

  /**
   * The badge colour for a report status. B13.
   *
   * It used to answer `verified`/`investigating`/`resolved` and default to `t.warn`
   * -- amber -- for everything else, which in practice meant every report the user
   * had ever filed wore a warning colour forever, because `pending` was the only
   * value anything ever wrote.
   *
   * `filed` is now `t.info`: neutral, "this is on record". Amber would be claiming
   * something is outstanding, and nothing is -- there is no queue and no approver.
   */
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'withdrawn':
        return t.textFaint;
      case 'removed':
        return t.danger;
      default:
        return t.info;
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
        <ActivityIndicator size="large" color={t.brand} />
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
          color={t.danger}
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
      {/* The ambient field, behind everything. `glassSurface` is a
          translucent fill and needs something to be translucent over —
          see the note in theme/surfaces.ts. */}
      <Aurora intensity="ambient" />
      {/* Header */}
      <Grad
        colors={g.aurora}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 1 }}
        style={[styles.header, { paddingTop: insets.top + space.lg }]}>
        <TouchableOpacity
          style={styles.headerButton}
          onPress={() => navigation.goBack()}
        >
          <Ionicons name="arrow-back" size={24} color={t.onBrand} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Report Details</Text>
        <View style={styles.headerActions}>
          {/* Withdraw before delete, and only while the report is on record. The
              gentler action sits first because it is the one that keeps the
              provenance of anything this report has already contributed to. */}
          {report?.status === 'filed' && (
            <TouchableOpacity
              style={styles.headerButton}
              onPress={handleWithdraw}
              accessibilityLabel="Withdraw this report"
            >
              <Ionicons name="eye-off-outline" size={24} color={t.onBrand} />
            </TouchableOpacity>
          )}
          <TouchableOpacity
            style={styles.headerButton}
            onPress={handleDelete}
            accessibilityLabel="Delete this report"
          >
            <Ionicons name="trash-outline" size={24} color={t.onBrand} />
          </TouchableOpacity>
        </View>
      </Grad>

      <ScrollView
        style={styles.content}
        contentContainerStyle={[
          styles.scrollContent,
          { paddingBottom: insets.bottom + space.xl },
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
            {/* The `✓` was gated on `report.verified`, a column nothing could ever
                set -- so it was a tick the UI promised and could not deliver. Both
                the column and the badge are gone; see contracts/crime.ts. */}
            {reportStatusLabel(report.status).toUpperCase()}
          </Text>
        </View>

        {/* Category Section */}
        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <MaterialCommunityIcons
              name={getCategoryIcon(report.category)}
              size={24}
              color={t.brand}
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
              color={t.brand}
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
              color={t.brand}
            />
            <Text style={styles.sectionTitle}>Description</Text>
          </View>
          <Text style={styles.contentText}>{report.description}</Text>
        </View>

        {/* Evidence photo and what D07 read out of it. Only shown when the
            report actually has one -- most do not. */}
        {!!report.evidence_photo_path && (
          <View style={styles.section}>
            <View style={styles.sectionHeader}>
              <MaterialCommunityIcons
                name="image-outline"
                size={24}
                color={t.brand}
              />
              <Text style={styles.sectionTitle}>Evidence photo</Text>
            </View>

            {photoUrl ? (
              <Image
                source={{ uri: photoUrl }}
                style={styles.evidenceImage}
                resizeMode="cover"
              />
            ) : (
              <Text style={styles.contentText}>
                Photo unavailable. It may have been removed.
              </Text>
            )}

            {!!report.vision_analysis?.description && (
              <>
                <Text style={styles.evidenceCaption}>
                  {report.vision_analysis.description}
                </Text>
                <Text style={styles.evidenceMeta}>
                  Read by {report.vision_analysis.engine}
                  {report.vision_analysis.proposed_category
                    ? `  ·  suggested ${report.vision_analysis.proposed_category}`
                    : '  ·  no category suggested'}
                  {report.vision_analysis.filed_category &&
                  report.vision_analysis.filed_category !==
                    report.vision_analysis.proposed_category
                    ? `  ·  reporter filed ${report.vision_analysis.filed_category}`
                    : ''}
                </Text>
              </>
            )}
          </View>
        )}

        {/* Date & Time Section */}
        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <Ionicons name="calendar" size={24} color={t.brand} />
            <Text style={styles.sectionTitle}>Incident Date & Time</Text>
          </View>
          <Text style={styles.contentText}>
            {formatDate(report.incident_date_time)}
          </Text>
        </View>

        {/* Location Section */}
        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <Ionicons name="location" size={24} color={t.brand} />
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
            // Follow the app's theme, not the phone's. See `MapComponent.tsx`.
            key={mode}
            userInterfaceStyle={mode}
            provider={MAP_PROVIDER}
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
              color={t.textSoft}
            />
            <Text style={styles.timestampLabel}>Reported: </Text>
            <Text style={styles.timestampValue}>
              {formatDate(report.created_at)}
            </Text>
          </View>
        </View>

        {/* D08 — the General Diary. A report is a record; this is what turns it
            into something a police station will accept. We draft it; the user
            signs and files it. */}
        <TouchableOpacity
          style={styles.gdButton}
          onPress={() => navigation.navigate('GdDraft', { reportId })}
        >
          <MaterialCommunityIcons
            name="file-document-edit-outline"
            size={22}
            color={t.onBrand}
          />
          <View style={styles.gdButtonText}>
            <Text style={styles.gdButtonTitle}>General Diary</Text>
            <Text style={styles.gdButtonSubtitle}>
              Turn this report into a formal Bangla GD application
            </Text>
          </View>
          <Ionicons name="chevron-forward" size={20} color={t.onBrand} />
        </TouchableOpacity>
      </ScrollView>
    </View>
  );
};

const makeStyles = (t: Palette) =>
StyleSheet.create({
    gdButton: {
      flexDirection: 'row',
      alignItems: 'center',
      backgroundColor: t.brand,
      borderRadius: radius.card,
      paddingVertical: space.lg,
      paddingHorizontal: space.lg,
      marginHorizontal: space.lg,
      marginTop: space.xl,
      marginBottom: space.xxl,
    },
    gdButtonText: { flex: 1, marginLeft: space.lg },
    gdButtonTitle: {      ...type.bodyStrong, color: t.onBrand,},
    gdButtonSubtitle: {
      ...type.caption,
      color: 'rgba(255,255,255,0.8)',
      marginTop: 2,
    },
    container: {
      flex: 1,
      backgroundColor: t.bg,
    },
    loadingContainer: {
      flex: 1,
      justifyContent: 'center',
      alignItems: 'center',
      backgroundColor: t.bg,
    },
    loadingText: {
      ...type.body,
      marginTop: space.lg,
      color: t.textSoft,
    },
    errorContainer: {
      flex: 1,
      justifyContent: 'center',
      alignItems: 'center',
      backgroundColor: t.bg,
      padding: space.xxl,
    },
    errorText: {
      ...type.body,
      color: t.danger,
      textAlign: 'center',
      marginTop: space.lg,
      marginBottom: space.xl,
    },
    retryButton: {
      backgroundColor: t.brand,
      paddingHorizontal: space.xxl,
      paddingVertical: space.lg,
      borderRadius: radius.md,
      marginBottom: space.lg,
    },
    retryButtonText: {
      ...type.bodyStrong,
      color: t.onBrand,
    },
    backButton: {
      backgroundColor: t.fillStrong,
      paddingHorizontal: space.xxl,
      paddingVertical: space.lg,
      borderRadius: radius.md,
    },
    backButtonText: {
      ...type.bodyStrong,
      color: t.text,
    },
    header: {
      flexDirection: 'row',
      justifyContent: 'space-between',
      alignItems: 'center',
      padding: space.xl,
    },
    headerButton: {
      width: 40,
      height: 40,
      justifyContent: 'center',
      alignItems: 'center',
    },
    // The header is a three-column row (back · title · actions) and the title is
    // centred by the two outer cells being equal. Two action buttons would make the
    // right cell wider than the left and pull the title off centre, so they share
    // one cell and the row keeps its balance whether there are one or two.
    headerActions: { flexDirection: 'row', alignItems: 'center' },
    headerTitle: {
      ...type.heading,
      color: t.onBrand,
    },
    content: {
      flex: 1,
    },
    scrollContent: {
      padding: space.xl,
    },
    statusBadge: {
      alignSelf: 'flex-start',
      paddingHorizontal: space.lg,
      paddingVertical: space.sm,
      borderRadius: radius.md,
      marginBottom: space.xl,
    },
    statusText: {
      ...type.bodyStrong,
      color: t.onBrand,
      letterSpacing: 1,
    },
    section: {
      ...glassSurface(t),
      padding: space.lg,
      marginBottom: space.lg,
      ...lift(t, 1),
    },
    sectionHeader: {
      flexDirection: 'row',
      alignItems: 'center',
      marginBottom: space.sm,
    },
    sectionTitle: {
      ...type.bodyStrong,
      color: t.text,
      marginLeft: space.sm,
    },
    categoryValue: {
      ...type.bodyStrong,
      color: t.brand,
      textTransform: 'capitalize',
    },
    contentText: {
      ...type.body,
      color: t.text,
    },
    coordinatesText: {
      ...type.small,
      color: t.textSoft,
      marginTop: space.xs,
      // The one deliberate exception to the type scale: a latitude and a
      // longitude are read digit by digit against each other, and a
      // proportional face makes that harder than it needs to be.
      fontFamily: 'monospace',
    },
    mapContainer: {
      height: 200,
      borderRadius: radius.md,
      overflow: 'hidden',
      marginBottom: space.lg,
      ...lift(t, 2),
    },
    map: {
      flex: 1,
    },
    timestampSection: {
      ...glassSurface(t),
      padding: space.lg,
      ...lift(t, 1),
    },
    timestampRow: {
      flexDirection: 'row',
      alignItems: 'center',
      marginBottom: space.xs,
    },
    timestampLabel: {
      ...type.small,
      color: t.textSoft,
      marginLeft: space.xs,
    },
    timestampValue: {
      ...type.small,
      color: t.text,
    },
    // --- D07: evidence photo -------------------------------------------------
    evidenceImage: {
      width: '100%',
      height: 220,
      borderRadius: radius.md,
      backgroundColor: t.fillSoft,
    },
    evidenceCaption: {
      ...type.body,
      color: t.text,
      marginTop: space.lg,
    },
    evidenceMeta: {
      ...type.caption,
      color: t.textSoft,
      marginTop: space.xs,
    },
  });

export default ReportDetailsScreen;
