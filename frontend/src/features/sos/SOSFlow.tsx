/**
 * The two modals an SOS puts on screen: the camera, then the progress overlay.
 *
 * Separate from `useSOS` so that a screen adds SOS with one element rather than
 * forty lines of copied JSX — which is how `MapScreen` ended up with a red button
 * and no implementation behind it (defect 14).
 */
import React from 'react';
import { View, Text, StyleSheet, Modal, ActivityIndicator } from 'react-native';
import { colors, spacing, borderRadius, typography, shadows } from '../../theme';
import { SOSCameraModal } from '../../components/SOSCameraModal';
import type { SosController } from './useSOS';

export const SOSFlow: React.FC<{ sos: SosController }> = ({ sos }) => (
  <>
    <SOSCameraModal
      visible={sos.cameraVisible}
      onClose={sos.cancel}
      onVideoRecorded={sos.onVideoRecorded}
      onError={sos.onCameraError}
    />

    <Modal transparent visible={sos.sending}>
      <View style={styles.overlay}>
        <View style={styles.card}>
          <ActivityIndicator size="large" color={colors.danger} />
          <Text style={styles.title}>
            {sos.stage === 'sending' ? 'Alerting your contacts...' : 'Uploading Evidence...'}
          </Text>

          <View style={styles.barTrack}>
            <View style={[styles.barFill, { width: `${sos.progress}%` }]} />
          </View>
          <Text style={styles.percent}>{sos.progress}% Completed</Text>

          <Text style={styles.subtitle}>
            {sos.stage === 'sending'
              ? 'Evidence uploaded. Sending the alert — do not close the app.'
              : 'Please do not close the app'}
          </Text>
        </View>
      </View>
    </Modal>
  </>
);

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.5)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  card: {
    backgroundColor: colors.white,
    padding: spacing.xl,
    borderRadius: borderRadius.md,
    alignItems: 'center',
    ...shadows.lg,
  },
  title: {
    ...typography.h4,
    color: colors.text,
    marginTop: spacing.md,
    fontWeight: 'bold',
  },
  subtitle: {
    ...typography.bodySmall,
    color: colors.textSecondary,
    textAlign: 'center',
  },
  barTrack: {
    width: 200,
    height: 8,
    backgroundColor: '#E5E7EB',
    borderRadius: 4,
    marginTop: spacing.md,
    marginBottom: spacing.xs,
    overflow: 'hidden',
  },
  barFill: {
    height: '100%',
    backgroundColor: colors.primary,
    borderRadius: 4,
  },
  percent: {
    ...typography.caption,
    color: colors.textSecondary,
    marginBottom: spacing.sm,
  },
});
