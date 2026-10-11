/**
 * `Sheet` — the one modal container. A scrim, and a pane of the app's material.
 *
 * ## Why this exists
 *
 * Every modal in the app was a hand-rolled `<Modal transparent>` wrapping a
 * `<View style={{ backgroundColor: t.surface }}>` with its own radius, its own
 * padding and its own idea of how dark the scrim should be. Eight of them, no
 * two alike, and none of them carrying the glass material that the rest of the
 * UI is built from — so opening any dialog dropped the user out of the new look
 * and into the old one. `theme/surfaces.ts` even lists "a modal" as a place the
 * `Glass` component belongs; nothing had done it.
 *
 * ## The blur is deliberately off
 *
 * `Glass` here is passed `blur={false}`, and that is not a performance trade —
 * it is a correctness one.
 *
 * On Android a `Modal` is a separate native **window**. React context crosses
 * the boundary (the children are in the same React tree), so `useBlurProps()`
 * cheerfully hands back the blur target belonging to the screen *underneath* —
 * a view in a different window. Dimezis would be asked to sample a node it
 * cannot see, and what comes back is undefined rather than wrong-but-pretty.
 *
 * iOS could blur the presenting screen correctly, through a real
 * `UIVisualEffectView`. Taking it there too keeps one code path and one
 * appearance, and the fill, the edge, the sheen and the shadow are what carry
 * the material anyway — see the four conditions in `Glass.tsx`.
 *
 * ## Two shapes, because there are two kinds of modal
 *
 * `center` is a decision: a result, a confirmation, a short form. It floats,
 * rounded on all four corners, with a maximum width so it does not stretch into
 * a band of text on a tablet.
 *
 * `bottom` is a detail: a risk flag, a route comparison, anything you have
 * *opened* rather than been *asked*. It is attached to the bottom edge, rounded
 * only at the top, and reaches at most three quarters up the screen so the
 * thing it describes stays visible behind it.
 */

import React from 'react';
import {
  KeyboardAvoidingView,
  Modal,
  Platform,
  Pressable,
  StyleSheet,
  View,
  type StyleProp,
  type ViewStyle,
} from 'react-native';

import { useTheme } from '../../theme/ThemeProvider';
import { Glass } from './Glass';

export type SheetVariant = 'center' | 'bottom';

export interface SheetProps {
  visible: boolean;
  /**
   * Android's back button and, when `dismissable`, a tap on the scrim.
   *
   * Optional: a sheet that reports the outcome of something irreversible — an
   * SOS that has been sent — should not be dismissable by a stray tap, and
   * leaving this out is how you say so.
   */
  onClose?: () => void;
  variant?: SheetVariant;
  /**
   * Whether tapping the scrim closes it. Off by default.
   *
   * On by default would be the usual choice, but the modals in this app are
   * mostly emergency flows, and "I dismissed the SOS confirmation by touching
   * the edge of the screen" is not a trade worth making for convenience.
   */
  dismissable?: boolean;
  /** `fade` for `center`, `slide` for `bottom`, unless told otherwise. */
  animationType?: 'none' | 'slide' | 'fade';
  children?: React.ReactNode;
  /** Lands on the pane. For a width, a margin, a `maxHeight`. */
  style?: StyleProp<ViewStyle>;
  /** Lands on the content box inside the padding — a `gap`, an `alignItems`. */
  contentStyle?: StyleProp<ViewStyle>;
  padding?: number;
  /** Overrides the shape's radius. Rarely wanted. */
  radius?: number;
  /**
   * Lift the pane above the keyboard. For a sheet containing a text input.
   *
   * Off by default because it is not free: `KeyboardAvoidingView` measures and
   * re-lays-out on every keyboard frame, and on a sheet with no input that is
   * work for nothing. The two behaviours differ by platform — iOS insets by
   * `padding`, Android resizes by `height` — which is the kind of detail that
   * gets copied wrong, so it lives here once.
   */
  avoidKeyboard?: boolean;
}

export const Sheet: React.FC<SheetProps> = ({
  visible,
  onClose,
  variant = 'center',
  dismissable = false,
  animationType,
  children,
  style,
  contentStyle,
  padding,
  radius: radiusProp,
  avoidKeyboard = false,
}) => {
  const { t, space, radius } = useTheme();
  const bottom = variant === 'bottom';
  const Frame = avoidKeyboard ? KeyboardAvoidingView : View;

  return (
    <Modal
      transparent
      visible={visible}
      animationType={animationType ?? (bottom ? 'slide' : 'fade')}
      onRequestClose={onClose}
      // Draws under the status bar instead of leaving an opaque strip above the
      // scrim, which on Android is what makes a dialog look bolted on.
      statusBarTranslucent
    >
      <Frame
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={[
          styles.scrim,
          { backgroundColor: t.scrim },
          bottom ? styles.alignBottom : styles.alignCenter,
          // A centred sheet needs room at the sides; a bottom one is flush.
          bottom ? null : { padding: space.lg },
        ]}
      >
        {/*
          The scrim's tap target is a sibling *behind* the pane, not a wrapper
          around it. Wrapping would put a Pressable between the scrim and the
          content, and on Android a parent Pressable swallows the touches of the
          buttons inside it often enough to be the first thing that breaks.
        */}
        {dismissable && onClose ? (
          <Pressable
            style={StyleSheet.absoluteFill}
            onPress={onClose}
            accessibilityRole="button"
            accessibilityLabel="Close"
          />
        ) : null}

        <Glass
          blur={false}
          elevated
          radius={radiusProp ?? (bottom ? radius.sheet : radius.card)}
          padding={padding}
          contentStyle={contentStyle}
          style={[bottom ? styles.bottomPane : styles.centerPane, style]}
        >
          {children}
        </Glass>
      </Frame>
    </Modal>
  );
};

const styles = StyleSheet.create({
  scrim: { flex: 1 },
  alignCenter: { justifyContent: 'center', alignItems: 'center' },
  alignBottom: { justifyContent: 'flex-end' },
  centerPane: {
    width: '100%',
    // 420 rather than a percentage: a dialog is read, and a line of text past
    // about 60 characters stops being comfortable however wide the screen is.
    maxWidth: 420,
  },
  bottomPane: {
    width: '100%',
    maxHeight: '78%',
    // Square at the bottom, because it is flush with the screen edge. A radius
    // there leaves two wedges of scrim in the corners, which reads as a bug.
    borderBottomLeftRadius: 0,
    borderBottomRightRadius: 0,
    borderBottomWidth: 0,
  },
});

export default Sheet;
