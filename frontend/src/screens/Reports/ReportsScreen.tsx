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
import { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useFocusEffect } from '@react-navigation/native';
import { ReportsStackParamList } from '../../types';
import { colors, spacing, borderRadius, fontSize } from '../../theme';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { supabase } from '../../lib/supabase';
import { crimeService } from '../../services/crime.service';

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
          <Text style={styles.statusText}>{item.status}</Text>
        </View>
      </View>

      {/* Title */}
      <Text style={styles.reportTitle} numberOfLines={1} ellipsizeMode="tail">
        {item.title}
      </Text>

      {/* Location - truncated to 2 lines */}
      <Text style={styles.location} numberOfLines={2} ellipsizeMode="tail">
        <Ionicons name="location" size={14} color={colors.textSecondary} />
        {' ' + truncateLocation(item.location_name)}
      </Text>

      {/* Date and Time */}
      <Text style={styles.date}>
        <Ionicons name="time-outline" size={14} color={colors.textSecondary} />
        {' ' + formatDateTime(item.incident_date_time)}
      </Text>
    </TouchableOpacity>
  );

  return (
    <View style={styles.container}>
      <View style={[styles.header, { paddingTop: insets.top + spacing.md }]}>
        <Text style={styles.title}>My Reports</Text>
        <TouchableOpacity
          style={styles.addButton}
          onPress={() => navigation.navigate('AddReport')}
        >
          <Ionicons name="add" size={24} color={colors.white} />
        </TouchableOpacity>
      </View>

      {loading ? (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={colors.primary} />
          <Text style={styles.loadingText}>Loading reports...</Text>
        </View>
      ) : (
        <FlatList
          data={reports}
          renderItem={renderReport}
          keyExtractor={item => item.id}
          contentContainerStyle={[
            styles.list,
            { paddingBottom: insets.bottom },
          ]}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={onRefresh}
              colors={[colors.primary]}
              tintColor={colors.primary}
            />
          }
          ListEmptyComponent={
            <View style={styles.emptyContainer}>
              <MaterialCommunityIcons
                name="file-document-alert-outline"
                size={64}
                color={colors.gray400}
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

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: spacing.lg,
    backgroundColor: colors.primary,
  },
  title: {
    fontSize: 24,
    fontWeight: 'bold',
    color: colors.white,
  },
  addButton: {
    backgroundColor: colors.secondary,
    width: 40,
    height: 40,
    borderRadius: 20,
    justifyContent: 'center',
    alignItems: 'center',
  },
  list: {
    padding: spacing.lg,
  },
  reportCard: {
    backgroundColor: colors.surface,
    borderRadius: borderRadius.md,
    padding: spacing.md,
    marginBottom: spacing.md,
    elevation: 2,
    shadowColor: colors.shadow,
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.1,
    shadowRadius: 2,
  },
  reportHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: spacing.sm,
  },
  categoryBadge: {
    backgroundColor: colors.primary,
    paddingHorizontal: spacing.sm,
    paddingVertical: 4,
    borderRadius: borderRadius.sm,
  },
  categoryText: {
    color: colors.white,
    fontSize: fontSize.sm,
    fontWeight: '600',
  },
  statusBadge: {
    paddingHorizontal: spacing.sm,
    paddingVertical: 4,
    borderRadius: borderRadius.sm,
  },
  statusText: {
    color: colors.white,
    fontSize: fontSize.sm,
    fontWeight: '600',
    textTransform: 'capitalize',
  },
  reportTitle: {
    fontSize: fontSize.lg,
    fontWeight: '600',
    color: colors.textPrimary,
    marginBottom: spacing.xs,
  },
  location: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    marginBottom: spacing.xs,
    lineHeight: 18,
  },
  date: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
  },
  emptyContainer: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: spacing.xxl,
  },
  emptyText: {
    fontSize: fontSize.lg,
    fontWeight: '600',
    color: colors.textSecondary,
    marginTop: spacing.md,
  },
  emptySubtext: {
    fontSize: fontSize.md,
    color: colors.textSecondary,
    marginTop: spacing.sm,
    textAlign: 'center',
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingVertical: spacing.xxl,
  },
  loadingText: {
    marginTop: spacing.md,
    fontSize: fontSize.md,
    color: colors.textSecondary,
  },
});

export default ReportsScreen;
