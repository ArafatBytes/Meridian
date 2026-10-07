import React, { useRef, useState, useEffect } from 'react';
import { View, StyleSheet, Text, Modal, TouchableOpacity, Alert, Animated, Easing } from 'react-native';
import { CameraView, useCameraPermissions } from 'expo-camera';
import { colors, spacing, typography } from '../theme';
import { Ionicons } from '@expo/vector-icons';

interface SOSCameraModalProps {
    visible: boolean;
    onClose: () => void;
    onVideoRecorded: (uri: string) => void;
    onError: (error: string) => void;
}

export const SOSCameraModal: React.FC<SOSCameraModalProps> = ({
    visible,
    onClose,
    onVideoRecorded,
    onError,
}) => {
    const [permission, requestPermission] = useCameraPermissions();
    const cameraRef = useRef<CameraView>(null);
    const [isRecording, setIsRecording] = useState(false);
    const [countdown, setCountdown] = useState(10);

    // Animation Value for Pulse
    const pulseAnim = useRef(new Animated.Value(1)).current;

    useEffect(() => {
        if (visible && !permission) {
            requestPermission();
        }
    }, [visible, permission]);

    useEffect(() => {
        if (isRecording) {
            Animated.loop(
                Animated.sequence([
                    Animated.timing(pulseAnim, {
                        toValue: 0.3,
                        duration: 800,
                        useNativeDriver: true,
                    }),
                    Animated.timing(pulseAnim, {
                        toValue: 1,
                        duration: 800,
                        useNativeDriver: true,
                    }),
                ])
            ).start();
        } else {
            pulseAnim.setValue(1);
        }
    }, [isRecording]);

    useEffect(() => {
        let timer: NodeJS.Timeout;
        if (isRecording && countdown > 0) {
            timer = setInterval(() => {
                setCountdown((prev) => prev - 1);
            }, 1000);
        } else if (countdown === 0 && isRecording) {
            stopRecording();
        }
        return () => clearInterval(timer);
    }, [isRecording, countdown]);

    const startRecording = async () => {
        if (cameraRef.current && !isRecording) {
            setIsRecording(true);
            try {
                const video = await cameraRef.current.recordAsync({
                    maxDuration: 10,
                });

                if (video?.uri) {
                    onVideoRecorded(video.uri);
                }
            } catch (e: any) {
                console.error('Recording error:', e);
                onError(e.message || 'Failed to record video');
                setIsRecording(false);
            }
        }
    };

    const stopRecording = () => {
        if (cameraRef.current && isRecording) {
            cameraRef.current.stopRecording();
            setIsRecording(false);
        }
    };

    const handleCameraReady = () => {
        if (visible && !isRecording && permission?.granted) {
            setTimeout(startRecording, 500);
        }
    };

    if (!visible) return null;

    if (!permission) {
        return <View />;
    }

    if (!permission.granted) {
        return (
            <Modal visible={visible} animationType="fade" transparent>
                <View style={styles.container}>
                    <View style={styles.permissionCard}>
                        <Ionicons name="camera" size={48} color={colors.textPrimary} style={{ marginBottom: 20 }} />
                        <Text style={styles.permissionTitle}>Camera Access Required</Text>
                        <Text style={styles.permissionText}>Meridian needs camera access to record emergency evidence.</Text>
                        <TouchableOpacity style={styles.button} onPress={requestPermission}>
                            <Text style={styles.buttonText}>Enable Camera</Text>
                        </TouchableOpacity>
                        <TouchableOpacity style={[styles.button, styles.cancelButton]} onPress={onClose}>
                            <Text style={styles.buttonTextSecondary}>Cancel</Text>
                        </TouchableOpacity>
                    </View>
                </View>
            </Modal>
        );
    }

    return (
        <Modal visible={visible} animationType="fade" onRequestClose={onClose}>
            <View style={styles.container}>
                <CameraView
                    style={styles.camera}
                    facing="back"
                    mode="video"
                    ref={cameraRef}
                    onCameraReady={handleCameraReady}
                />

                <View style={styles.overlay}>
                    <View style={styles.topBar}>
                        <View style={styles.badge}>
                            <Text style={styles.badgeText}>EMERGENCY MODE</Text>
                        </View>
                    </View>

                    <View style={styles.centerContent}>
                        <Text style={styles.timerLarge}>{countdown}</Text>
                        <View style={styles.recordingIndicator}>
                            <Animated.View style={[styles.redDot, { opacity: pulseAnim }]} />
                            <Text style={styles.recordingText}>Recording Evidence...</Text>
                        </View>
                    </View>

                    <View style={styles.bottomBar}>
                        <Text style={styles.footerText}>Video sends automatically in 10s</Text>
                    </View>
                </View>
            </View>
        </Modal>
    );
};

const styles = StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: 'black',
    },
    camera: {
        ...StyleSheet.absoluteFill,  // RN 0.86 removed absoluteFillObject; absoluteFill is now the plain object
    },
    overlay: {
        ...StyleSheet.absoluteFill,  // RN 0.86 removed absoluteFillObject; absoluteFill is now the plain object
        backgroundColor: 'rgba(0,0,0,0.5)',
        justifyContent: 'space-between',
        padding: 30,
    },
    topBar: {
        alignItems: 'center',
        marginTop: 60,
    },
    badge: {
        backgroundColor: 'rgba(239, 68, 68, 0.9)',
        paddingVertical: 8,
        paddingHorizontal: 20,
        borderRadius: 30,
        borderWidth: 1,
        borderColor: 'rgba(255,255,255,0.2)',
    },
    badgeText: {
        color: 'white',
        fontWeight: '600',
        fontSize: 13,
        letterSpacing: 2,
    },
    centerContent: {
        alignItems: 'center',
        justifyContent: 'center',
    },
    timerLarge: {
        color: 'white',
        fontSize: 120,
        fontWeight: '200',
        fontVariant: ['tabular-nums'],
        textShadowColor: 'rgba(0,0,0,0.3)',
        textShadowOffset: { width: 0, height: 2 },
        textShadowRadius: 4,
    },
    recordingIndicator: {
        flexDirection: 'row',
        alignItems: 'center',
        marginTop: 10,
        backgroundColor: 'rgba(0,0,0,0.3)',
        paddingVertical: 8,
        paddingHorizontal: 16,
        borderRadius: 20,
    },
    redDot: {
        width: 10,
        height: 10,
        borderRadius: 5,
        backgroundColor: '#F87171',
        marginRight: 10,
    },
    recordingText: {
        color: '#E5E7EB',
        fontSize: 16,
        fontWeight: '500',
        letterSpacing: 0.5,
    },
    bottomBar: {
        alignItems: 'center',
        marginBottom: 50,
    },
    footerText: {
        color: 'rgba(255,255,255,0.6)',
        fontSize: 14,
        fontWeight: '500',
    },
    permissionCard: {
        backgroundColor: 'white',
        padding: 30,
        borderRadius: 16,
        alignItems: 'center',
        width: '85%',
        alignSelf: 'center',
        marginTop: '50%',
        elevation: 5,
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 4 },
        shadowOpacity: 0.1,
        shadowRadius: 12,
    },
    permissionTitle: {
        fontSize: 20,
        fontWeight: '700',
        marginBottom: 10,
        color: '#111827',
    },
    permissionText: {
        textAlign: 'center',
        color: '#6B7280',
        marginBottom: 24,
        lineHeight: 22,
        fontSize: 16,
    },
    button: {
        backgroundColor: '#111827',
        paddingVertical: 14,
        borderRadius: 12,
        width: '100%',
        alignItems: 'center',
        marginBottom: 12,
    },
    cancelButton: {
        backgroundColor: 'transparent',
        borderWidth: 1,
        borderColor: '#E5E7EB',
    },
    buttonText: {
        color: 'white',
        fontWeight: '600',
        fontSize: 16,
    },
    buttonTextSecondary: {
        color: '#374151',
        fontWeight: '600',
        fontSize: 16,
    }
});
