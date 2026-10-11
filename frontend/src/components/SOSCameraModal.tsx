import React, { useRef, useState, useEffect } from 'react';
import { View, StyleSheet, Text, Modal, TouchableOpacity, Alert, Animated, Easing, Platform } from 'react-native';
import { CameraView, useCameraPermissions, useMicrophonePermissions } from 'expo-camera';
import { colors, spacing, typography } from '../theme';
import { Ionicons } from '@expo/vector-icons';
import {
    SOS_VIDEO_BITRATE,
    SOS_VIDEO_DURATION_SECONDS,
    SOS_VIDEO_MAX_BYTES,
} from '../constants';

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
    // `recordAsync` records audio by default, and on Android that needs the
    // RECORD_AUDIO **runtime** grant -- declaring it in the manifest is not
    // enough. Nothing ever requested it here, so on a device where voice SOS had
    // not already asked for the microphone, recording failed with
    // "Video recording failed" and no indication why.
    const [micPermission, requestMicPermission] = useMicrophonePermissions();
    const cameraRef = useRef<CameraView>(null);

    /**
     * Whether a recording has been started for this opening of the modal.
     *
     * **A ref, because React state cannot do this job**, and that was the bug:
     *
     * `onCameraReady` fires more than once — reliably so, since changing any
     * capture prop reconfigures the session and re-fires it. Each call read
     * `isRecording` from *state*, i.e. from the closure of the render it was
     * created in. Two calls arriving before the first `setIsRecording(true)` had
     * rendered both saw `false`, both scheduled a start, and both of those
     * closures ALSO saw `false` — so both called `recordAsync`:
     *
     *     java.lang.IllegalStateException: A recording is already in progress.
     *
     * The second call then failed, its retries failed the same way, and
     * `onError` closed the modal — abandoning the first recording, which had
     * been working the whole time. That is why the log showed three
     * IllegalStateExceptions followed by "returned no file".
     *
     * A ref is written synchronously, so the second caller sees it immediately
     * and bails. There is no render in between to lose the fact.
     */
    const startLatchRef = useRef(false);
    const [isRecording, setIsRecording] = useState(false);
    // Seeded from the constant, not a literal 10 — they were already out of step
    // with each other, and the on-screen timer is what the user watches.
    const [countdown, setCountdown] = useState(SOS_VIDEO_DURATION_SECONDS);

    // Animation Value for Pulse
    const pulseAnim = useRef(new Animated.Value(1)).current;

    // Reset the countdown every time the modal opens. **This is the fix for
    // "Video recording failed: Unknown error" on the second SOS.**
    //
    // `if (!visible) return null` further down is an early return *inside* this
    // component, so hiding the modal does not unmount it — and `useState(10)`
    // only initialises once per mount. So after one SOS, `countdown` is left at
    // 0 forever.
    //
    // On the next SOS, `startRecording` sets `isRecording` true, the countdown
    // effect below immediately matches `countdown === 0 && isRecording`, and
    // calls `stopRecording()` **milliseconds after recording began**. CameraX
    // finalises with `ERROR_NO_VALID_DATA`, whose `cause` is null, so
    // expo-camera reports it as `"Video recording failed: Unknown error"` —
    // a message that says nothing about a ten-second timer having already
    // expired before the recording started.
    //
    // Every SOS after the first one in an app session failed this way. It
    // survived D01–D09 because one SOS per session is the normal way to test it.
    useEffect(() => {
        if (!visible) return;
        setCountdown(SOS_VIDEO_DURATION_SECONDS);
        setIsRecording(false);
        startLatchRef.current = false;
    }, [visible]);

    useEffect(() => {
        if (!visible) return;
        if (!permission) {
            requestPermission();
        }
        // Asked for separately and NOT gated on: a refused microphone means a
        // silent video, not a failed SOS. The camera still records.
        if (!micPermission) {
            requestMicPermission();
        }
    }, [visible, permission, micPermission]);

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

    /**
     * Record the SOS clip. Called once per opening of the modal.
     *
     * Idempotent via `startLatchRef`: a second concurrent call returns
     * immediately rather than throwing `IllegalStateException`. See that ref for
     * why state was not enough.
     *
     * One retry, not three. The earlier three-attempt chain was built on a wrong
     * guess — that the encoder configuration was at fault — and it varied only
     * the `recordAsync` options while `videoQuality` and `videoBitrate` (which
     * are CameraView *props*) stayed constant across every attempt. So it never
     * tested the thing it was built to test, and when the real fault turned out
     * to be a double start it retried straight into the same exception twice
     * more. A fallback that cannot tell "try again" from "stop trying" is worse
     * than none.
     */
    const startRecording = async () => {
        if (!cameraRef.current) return;
        // Synchronous, before any await. This is the whole fix.
        if (startLatchRef.current) {
            console.log('SOS camera: ignoring a duplicate start — one is already running.');
            return;
        }
        startLatchRef.current = true;
        setIsRecording(true);

        // `codec` is **iOS only** (expo-camera's types say `@platform ios`), and
        // on iOS it is what makes `videoBitrate` apply at all.
        const iosCodec = Platform.OS === 'ios' ? { codec: 'avc1' as const } : {};

        const attempts: { label: string; options: Record<string, unknown> }[] = [
            {
                label: 'tuned (duration + size cap)',
                options: {
                    maxDuration: SOS_VIDEO_DURATION_SECONDS,
                    maxFileSize: SOS_VIDEO_MAX_BYTES,
                    ...iosCodec,
                },
            },
            // Dropping `maxFileSize` is the one retry worth having: it is the
            // option most likely to be rejected by a given encoder, and the
            // duration cap alone still bounds the clip.
            {
                label: 'duration cap only',
                options: { maxDuration: SOS_VIDEO_DURATION_SECONDS, ...iosCodec },
            },
        ];

        let lastMessage = '';
        for (const attempt of attempts) {
            const camera = cameraRef.current;
            if (!camera) {
                lastMessage = 'The camera closed before recording could start.';
                console.error(`SOS camera: "${attempt.label}" skipped — camera gone.`);
                break;
            }
            try {
                const video = await camera.recordAsync(attempt.options);
                if (video?.uri) {
                    if (attempt.label !== attempts[0].label) {
                        console.warn(`SOS video recorded via fallback: ${attempt.label}`);
                    }
                    onVideoRecorded(video.uri);
                    return;
                }
                // Resolving without a file means something stopped the recording
                // — almost always `stopRecording()` from the countdown. Retrying
                // would race the same thing again.
                lastMessage = 'The recording was stopped before any video was written.';
                console.error(`SOS camera: "${attempt.label}" returned no file.`);
                break;
            } catch (problem: unknown) {
                lastMessage = problem instanceof Error ? problem.message : String(problem);
                console.error(`SOS camera: "${attempt.label}" failed:`, problem);
                // Never retry this one. It means a recording IS running, so the
                // right move is to leave it alone — retrying is what abandoned a
                // working recording last time.
                if (/already in progress/i.test(lastMessage)) {
                    console.warn('SOS camera: a recording is already running; leaving it be.');
                    return;
                }
            }
        }

        startLatchRef.current = false;
        setIsRecording(false);
        onError(
            `${lastMessage} Check that camera and microphone are allowed for ` +
                'Meridian in Android settings, and that no other app is using the camera.',
        );
    };

    const stopRecording = () => {
        if (cameraRef.current && isRecording) {
            cameraRef.current.stopRecording();
            setIsRecording(false);
        }
    };

    const handleCameraReady = () => {
        // `startLatchRef`, not `isRecording`: this fires more than once and the
        // state has not necessarily rendered yet between calls. `startRecording`
        // latches again itself, so this is belt and braces — but it also avoids
        // queueing a second pointless timeout.
        if (!visible || startLatchRef.current || !permission?.granted) return;
        setTimeout(startRecording, 500);
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
                    // Muted only when the microphone was actually refused.
                    // Toggling this mid-failure as a retry strategy was a mistake:
                    // `mute` is a prop, so changing it reconfigures the capture
                    // session, which aborts the very recording it was trying to
                    // rescue. The retries vary the *options* instead.
                    mute={micPermission?.granted === false}
                    ref={cameraRef}
                    onCameraReady={handleCameraReady}
                    // Keep the clip small enough to actually send. Default quality
                    // produced 16.45 MB for 10 seconds, which took 2m34s to email.
                    //
                    // videoQuality's 16:9 options are Android-only; '4:3' is the
                    // cross-platform one and means 640x480. videoBitrate is what
                    // does the work on iOS, together with the codec passed to
                    // recordAsync.
                    // ANDROID: neither. Let CameraX choose.
                    //
                    // Evidence, from logcat on a Unisoc ums9230 (Vivo V2344):
                    // the recording ran its full 10 seconds, audio was captured
                    // the whole time, and `Recorder` logged "Cached audio data
                    // while we wait for video keyframe before starting muxer"
                    // **43 times a second for all ten seconds**. Not one video
                    // frame ever reached the encoder, so the muxer never started
                    // and there was no valid data to write — which expo-camera
                    // reports as "Video recording failed: Unknown error".
                    //
                    // The encoder was configured correctly (bitrate 1440000,
                    // c2.unisoc.avc.encoder) and audio worked. What failed was
                    // frame delivery to the VideoCapture surface, and the one
                    // lever available for that from JS is the requested quality:
                    // `'4:3'` maps to `Quality.LOWEST` and `'480p'` to
                    // `Quality.SD`, both of which the device may simply not
                    // produce for a video stream. Unset, expo-camera asks for its
                    // default 1080p and CameraX negotiates what the camera can
                    // actually deliver.
                    //
                    // The size guarantee moves to `maxFileSize`, and CameraX
                    // treats ERROR_FILE_SIZE_LIMIT_REACHED as a successful
                    // finish — a truncated clip rather than a lost one.
                    //
                    // iOS keeps the measured values: 4:3 at 1.2 Mbps, which is
                    // what stopped a 10-second clip being 16.45 MB and taking
                    // 2m34s to email.
                    videoQuality={Platform.OS === 'android' ? undefined : '4:3'}
                    videoBitrate={Platform.OS === 'android' ? undefined : SOS_VIDEO_BITRATE}
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
