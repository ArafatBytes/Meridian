/**
 * `Dialog` — the app saying something, in the app's own material.
 *
 * ## Why this is not `Alert.alert`
 *
 * `Alert.alert` draws the *operating system's* dialog. On Android that is a
 * Material 3 box with Roboto, the platform's accent colour and square-ish
 * corners; on iOS it is a UIAlertController. Neither has ever seen `palette.ts`.
 * So the one moment the app most needs to look deliberate — when it is telling
 * you something went wrong — is the one moment it drops out of its own skin and
 * into the phone's. It also ignores the dark theme entirely on some Android
 * skins, which is how you get a white box over a dark map.
 *
 * `Sheet` already solved the container problem: one scrim, one pane, the glass
 * material, the right radius. This is that, with the two or three things an
 * alert actually needs — a title, a sentence, and a way out.
 *
 * ## It is deliberately not a drop-in `Alert.alert`
 *
 * `Alert.alert` is imperative: you call it from anywhere, including a `catch`.
 * A React component cannot be, so the caller holds the message in state and
 * renders this. That is more lines at the call site, and it buys the thing the
 * imperative version cannot give: the dialog is part of the render, so it
 * cannot outlive the screen that raised it and cannot stack two deep.
 *
 * ## The tone is a colour and nothing else
 *
 * No tone makes the dialog dismissable-by-scrim or not, and none of them change
 * the buttons. A dialog that behaves differently depending on an adjective is a
 * dialog you have to read the source of before you trust it.
 */

import { Ionicons } from '@expo/vector-icons';
import React from 'react';
import { StyleSheet, Text, TouchableOpacity, View } from 'react-native';

import { Sheet } from './motion';
import { useTheme } from '../theme/ThemeProvider';

export type DialogTone = 'info' | 'warn' | 'danger';

export interface DialogAction {
  label: string;
  onPress?: () => void;
  /** The filled one. At most one per dialog; the last action if none is marked. */
  primary?: boolean;
}

export interface DialogProps {
  /** Nothing renders at all when false — see `Sheet`, which owns the `Modal`. */
  visible: boolean;
  title: string;
  /** The body. One or two sentences; this is not a place for a paragraph. */
  message?: string;
  tone?: DialogTone;
  /**
   * Overrides the glyph the tone picks. Rarely wanted — the tone's own icon is
   * what makes a warning recognisable before it is read.
   */
  icon?: keyof typeof Ionicons.glyphMap;
  /** Defaults to a single "OK" that calls `onClose`. */
  actions?: DialogAction[];
  /** Android back, the scrim, and whatever an action does after its `onPress`. */
  onClose: () => void;
}

const GLYPH: Record<DialogTone, keyof typeof Ionicons.glyphMap> = {
  info: 'information-circle',
  warn: 'alert-circle',
  danger: 'warning',
};

export const Dialog: React.FC<DialogProps> = ({
  visible,
  title,
  message,
  tone = 'info',
  icon,
  actions,
  onClose,
}) => {
  const { t, type, space, radius } = useTheme();

  const accent = tone === 'danger' ? t.danger : tone === 'warn' ? t.warn : t.brand;
  const accentSoft = tone === 'danger' ? t.dangerSoft : tone === 'warn' ? t.warnSoft : t.brandSoft;

  const buttons: DialogAction[] = actions?.length ? actions : [{ label: 'OK', primary: true }];
  // The last one is primary unless somebody said otherwise, because the
  // rightmost button is where a thumb goes and the affirmative belongs there.
  const primaryIndex = buttons.some(a => a.primary)
    ? buttons.findIndex(a => a.primary)
    : buttons.length - 1;

  return (
    <Sheet
      visible={visible}
      onClose={onClose}
      variant="center"
      dismissable
      padding={space.xl}
      contentStyle={{ gap: space.md }}
    >
      <View style={[styles.head, { gap: space.md }]}>
        <View
          style={[
            styles.badge,
            { backgroundColor: accentSoft, borderRadius: radius.md },
          ]}
        >
          <Ionicons name={icon ?? GLYPH[tone]} size={20} color={accent} />
        </View>
        {/* `flex: 1` and no `numberOfLines`: a title that needs two lines gets
            two lines. Truncating the one sentence that says what happened is
            the opposite of the point. */}
        <Text style={[type.heading, styles.title, { color: t.text }]}>{title}</Text>
      </View>

      {message ? (
        <Text style={[type.body, { color: t.textSoft }]}>{message}</Text>
      ) : null}

      <View style={[styles.actions, { gap: space.sm, marginTop: space.xs }]}>
        {buttons.map((action, i) => {
          const isPrimary = i === primaryIndex;
          return (
            <TouchableOpacity
              key={action.label}
              onPress={() => {
                // Closed first, then the handler: an `onPress` that navigates
                // would otherwise leave a modal window open over the screen it
                // left, which on Android is unrecoverable without a back press.
                onClose();
                action.onPress?.();
              }}
              accessibilityRole="button"
              style={[
                styles.button,
                {
                  paddingHorizontal: space.lg,
                  borderRadius: radius.md,
                  backgroundColor: isPrimary ? accent : t.fillSoft,
                },
              ]}
            >
              <Text
                style={[
                  type.label,
                  { color: isPrimary ? t.onBrand : t.textSoft },
                ]}
              >
                {action.label}
              </Text>
            </TouchableOpacity>
          );
        })}
      </View>
    </Sheet>
  );
};

const styles = StyleSheet.create({
  head: { flexDirection: 'row', alignItems: 'center' },
  badge: { width: 36, height: 36, alignItems: 'center', justifyContent: 'center' },
  title: { flex: 1 },
  actions: { flexDirection: 'row', justifyContent: 'flex-end' },
  // 44, because this is the only tap target on the screen while it is open.
  button: { minHeight: 44, alignItems: 'center', justifyContent: 'center' },
});

export default Dialog;
