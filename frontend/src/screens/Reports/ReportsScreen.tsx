import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  ActivityIndicator,
  RefreshControl,
} from 'react-native';
import { Ionicons, MaterialCommunityIcons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useFocusEffect } from '@react-navigation/native';
import { ReportsStackParamList } from '../../types';
import { useTheme } from '../../theme/ThemeProvider';
import { useStyles } from '../../theme/useStyles';
import type { Palette } from '../../theme/palette';
import { glassSurface, lift } from '../../theme/surfaces';
import { Aurora } from '../../components/motion';
import { fontFamily, radius, space, type } from '../../theme/type';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { TAB_BAR_CLEARANCE } from '../../navigation/metrics';
import { supabase } from '../../lib/supabase';
import { crimeService } from '../../services/crime.service';
import { reportStatusLabel } from '../../types/contracts/crime';

// @ts-ignore - generated types fight `style` in this RN version
const Grad = LinearGradient as any;

type ReportsScreenNavigationProp = NativeStackNavigationProp<
  ReportsStackParamList,
  'MyReports'
>;

interface Props {
  navigation: ReportsScreenNavigationProp;
}

interface Report {
  id: string;
  category: string;
  title: string;
  incident_date_time: string;
  status: string;
  location_name: string;
  created_at: string;
}

const ReportsScreen: React.FC<Props> = ({ navigation }) => {
  const { t, g } = useTheme();
  const styles = useStyles(makeStyles);
  const insets = useSafeAreaInsets();
  const [reports, setReports] = useState<Report[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchReports();
  }, []);

  // Refresh reports when screen comes into focus
  useFocusEffect(
    useCallback(() => {
      fetchReports();
    }, []),
  );

  const fetchReports = async () => {
    try {
      setError(null);
      const {
        data: { user },
        error: userError,
      } = await supabase.auth.getUser();

      if (userError || !user) {
        setError('User not authenticated');
        setReports([]);
        return;
      }

      const data = await crimeService.getUserReports(user.id);
      setReports(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load reports');
      setReports([]);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const onRefresh = () => {
    setRefreshing(true);
    fetchReports();
  };

  const formatDateTime = (dateString: string) => {
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

    // Format month name
    const monthNames = [
      'Jan',
      'Feb',
      'Mar',
      'Apr',
      'May',
      'Jun',
      'Jul',
      'Aug',
      'Sep',
      'Oct',
      'Nov',
      'Dec',
    ];
    const monthName = monthNames[parseInt(month, 10) - 1];

    return `${monthName} ${parseInt(day, 10)}, ${year}, ${hour12}:${minutes} ${ampm}`;
  };

  const truncateLocation = (location: string, maxLines: number = 2) => {
    if (!location) return 'Location not specified';
    // Estimate ~40 characters per line
    const maxLength = maxLines * 40;
    if (location.length <= maxLength) return location;
    return location.substring(0, maxLength - 4) + '....';
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

  const renderReport = ({ item }: { item: Report }) => (
    <TouchableOpacity
      style={styles.reportCard}
      onPress={() =>
        navigation.navigate('ReportDetails', { reportId: item.id })
      }
    >
      <View style={styles.reportHeader}>
        <View style={styles.categoryBadge}>
          <Text style={styles.categoryText}>{item.category.toUpperCase()}</Text>
        </View>
        <View
          style={[
            styles.statusBadge,
            { backgroundColor: getStatusColor(item.status) },
          ]}
        >
          <Text style={styles.statusText}>
            {reportStatusLabel(item.status)}
          </Text>
        </View>
      </View>

      {/* Title */}
      <Text style={styles.reportTitle} numberOfLines={1} ellipsizeMode="tail">
        {item.title}
      </Text>

      {/* Location - truncated to 2 lines */}
      <Text style={styles.location} numberOfLines={2} ellipsizeMode="tail">
        <Ionicons name="location" size={14} color={t.textSoft} />
        {' ' + truncateLocation(item.location_name)}
      </Text>

      {/* Date and Time */}
      <Text style={styles.date}>
        <Ionicons name="time-outline" size={14} color={t.textSoft} />
        {' ' + formatDateTime(item.incident_date_time)}
      </Text>
    </TouchableOpacity>
  );

  return (
    <View style={styles.container}>
      {/* The ambient field, behind everything. `glassSurface` is a
          translucent fill and needs something to be translucent over —
          see the note in theme/surfaces.ts. */}
      <Aurora intensity="ambient" />
      <Grad
        colors={g.aurora}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 1 }}
        style={[styles.header, { paddingTop: insets.top + space.lg }]}>
        <Text style={styles.title}>My Reports</Text>
        <TouchableOpacity
          style={styles.addButton}
          onPress={() => navigation.navigate('AddReport')}
        >
          <Ionicons name="add" size={24} color={t.onBrand} />
        </TouchableOpacity>
      </Grad>

      {loading ? (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={t.brand} />
          <Text style={styles.loadingText}>Loading reports...</Text>
        </View>
      ) : (
        <FlatList
          data={reports}
          renderItem={renderReport}
          keyExtractor={item => item.id}
          contentContainerStyle={[
            styles.list,
            { paddingBottom: insets.bottom + TAB_BAR_CLEARANCE },
          ]}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={onRefresh}
              colors={[t.brand]}
              tintColor={t.brand}
            />
          }
          ListEmptyComponent={
            <View style={styles.emptyContainer}>
              <MaterialCommunityIcons
                name="file-document-alert-outline"
                size={64}
                color={t.textFaint}
              />
              <Text style={styles.emptyText}>
                {error ? error : 'No reports yet'}
              </Text>
              <Text style={styles.emptySubtext}>
                {error
                  ? 'Pull down to refresh'
                  : 'Tap + to report a crime in your area'}
              </Text>
            </View>
          }
        />
      )}
    </View>
  );
};

const makeStyles = (t: Palette) =>
StyleSheet.create({
    container: {
      flex: 1,
      backgroundColor: t.bg,
    },
    header: {
      flexDirection: 'row',
      justifyContent: 'space-between',
      alignItems: 'center',
      padding: space.xl,
    },
    title: {
      fontFamily: fontFamily.display,
      fontSize: 24,
      color: t.onBrand,
    },
    addButton: {
      backgroundColor: t.accent,
      width: 40,
      height: 40,
      borderRadius: 20,
      justifyContent: 'center',
      alignItems: 'center',
    },
    list: {
      padding: space.xl,
    },
    reportCard: {
      ...glassSurface(t),
      padding: space.lg,
      marginBottom: space.lg,
      ...lift(t, 1),
    },
    reportHeader: {
      flexDirection: 'row',
      justifyContent: 'space-between',
      marginBottom: space.sm,
    },
    categoryBadge: {
      backgroundColor: t.brand,
      paddingHorizontal: space.sm,
      paddingVertical: 4,
      borderRadius: radius.sm,
    },
    categoryText: {
      ...type.label,
      color: t.onBrand,
    },
    statusBadge: {
      paddingHorizontal: space.sm,
      paddingVertical: 4,
      borderRadius: radius.sm,
    },
    statusText: {
      ...type.label,
      color: t.onBrand,
      textTransform: 'capitalize',
    },
    reportTitle: {
      ...type.bodyStrong,
      color: t.text,
      marginBottom: space.xs,
    },
    location: {
      ...type.small,
      color: t.textSoft,
      marginBottom: space.xs,
    },
    date: {
      ...type.small,
      color: t.textSoft,
    },
    emptyContainer: {
      alignItems: 'center',
      justifyContent: 'center',
      paddingVertical: space.huge,
    },
    emptyText: {
      ...type.bodyStrong,
      color: t.textSoft,
      marginTop: space.lg,
    },
    emptySubtext: {
      ...type.body,
      color: t.textSoft,
      marginTop: space.sm,
      textAlign: 'center',
    },
    loadingContainer: {
      flex: 1,
      justifyContent: 'center',
      alignItems: 'center',
      paddingVertical: space.huge,
    },
    loadingText: {
      ...type.body,
      marginTop: space.lg,
      color: t.textSoft,
    },
  });

export default ReportsScreen;
