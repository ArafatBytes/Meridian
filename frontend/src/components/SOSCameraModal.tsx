import React, { useRef, useState, useEffect } from 'react';
import { View, StyleSheet, Text, Modal, TouchableOpacity, Animated, Easing, Platform } from 'react-native';
import { CameraView, useCameraPermissions, useMicrophonePermissions } from 'expo-camera';
import { useTheme } from '../theme/ThemeProvider';
import { useStyles } from '../theme/useStyles';
import type { Palette } from '../theme/palette';
import { fontFamily, radius, space, type } from '../theme/type';
import { Sheet } from './motion';
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
  const { t } = useTheme();
  const styles = useStyles(makeStyles);
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
            // The permission card is a dialog, so it is a `Sheet` like every
            // other dialog in the app. It used to be a white box on a black
            // full-screen `container` -- the viewfinder's backdrop, reused --
            // which in dark mode was the brightest thing on the phone.
            <Sheet visible={visible} onClose={onClose} contentStyle={styles.permissionCard}>
                <Ionicons name="camera" size={48} color={t.textSoft} style={styles.permissionIcon} />
                <Text style={styles.permissionTitle}>Camera Access Required</Text>
                <Text style={styles.permissionText}>Meridian needs camera access to record emergency evidence.</Text>
                <TouchableOpacity style={styles.button} onPress={requestPermission}>
                    <Text style={styles.buttonText}>Enable Camera</Text>
                </TouchableOpacity>
                <TouchableOpacity style={[styles.button, styles.cancelButton]} onPress={onClose}>
                    <Text style={styles.buttonTextSecondary}>Cancel</Text>
                </TouchableOpacity>
            </Sheet>
        );
    }

    // Deliberately NOT a `Sheet`. A viewfinder is the whole screen and its
    // backdrop is the camera feed; a translucent pane over it would be a pane
    // over the thing the user is trying to see.
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
                    // ANDROID: bitrate yes, quality no. They are separate
                    // knobs and only one of them was at fault.
                    //
                    // Dropping the bitrate too is what made every Android clip
                    // four seconds long. With `videoBitrate` unset, expo-camera
                    // never calls `setTargetVideoEncodingBitRate`, so CameraX
                    // uses its own default for the quality it chose -- and with
                    // `videoQuality` unset that is 1080p, around 17 Mbps. That
                    // fills the 8 MB `maxFileSize` in **3.8 seconds**, CameraX
                    // finalises with `ERROR_FILE_SIZE_LIMIT_REACHED`, and
                    // `ExpoCameraView.kt` resolves that case as a SUCCESS with a
                    // uri. So the app got a valid four-second video, closed the
                    // modal, and left the countdown frozen at 6 -- nothing
                    // reported an error, because by the camera's lights nothing
                    // went wrong.
                    //
                    // The bitrate is what keeps the clip inside the size budget;
                    // `maxFileSize` is only the backstop. At 1.2 Mbps ten
                    // seconds is about 1.5 MB, so the cap stops binding and the
                    // upload is seconds rather than minutes.
                    //
                    // Quality stays unset, which is the part of the Vivo fix that
                    // was right. Evidence, from logcat on a Unisoc ums9230
                    // (Vivo V2344):
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
                    // 1.2 Mbps is the measured value that stopped a 10-second
                    // clip being 16.45 MB and taking 2m34s to email. iOS also
                    // pins the quality to 4:3, and needs the codec passed to
                    // `recordAsync` for the bitrate to apply at all.
                    videoQuality={Platform.OS === 'android' ? undefined : '4:3'}
                    videoBitrate={SOS_VIDEO_BITRATE}
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

const makeStyles = (t: Palette) =>
StyleSheet.create({
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
      fontFamily: fontFamily.bodySemi,
      color: 'white',
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
      fontFamily: fontFamily.bodyMedium,
      color: '#E5E7EB',
      fontSize: 16,
      letterSpacing: 0.5,
    },
    bottomBar: {
      alignItems: 'center',
      marginBottom: 50,
    },
    footerText: {
      fontFamily: fontFamily.bodyMedium,
      color: 'rgba(255,255,255,0.6)',
      fontSize: 14,
    },
    // The card's fill, radius, edge and shadow come from `Sheet` now. This is
    // only the arrangement of what is inside it.
    permissionCard: { alignItems: 'center' },
    permissionIcon: { marginBottom: space.lg },
    permissionTitle: {
      ...type.heading,
      marginBottom: space.sm,
      color: t.text,
    },
    permissionText: {
      ...type.body,
      textAlign: 'center',
      color: t.textSoft,
      marginBottom: space.xl,
    },
    button: {
      backgroundColor: t.brand,
      paddingVertical: space.md,
      borderRadius: radius.md,
      width: '100%',
      alignItems: 'center',
      marginBottom: space.md,
    },
    cancelButton: {
      backgroundColor: 'transparent',
      borderWidth: StyleSheet.hairlineWidth * 2,
      borderColor: t.line,
    },
    buttonText: {
      ...type.bodyStrong,
      color: t.onBrand,
    },
    buttonTextSecondary: {
      ...type.bodyStrong,
      color: t.textSoft,
    }
  });
