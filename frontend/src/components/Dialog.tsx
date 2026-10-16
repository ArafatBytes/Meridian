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
  /**
   * Only drawn when the actions are stacked, where each one is a full-width row
   * with space for it. In a two-button row an icon is decoration competing with
   * the one the title already has.
   */
  icon?: keyof typeof Ionicons.glyphMap;
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

  // Three or more will not fit side by side at phone width without truncating
  // the labels, and a choice you cannot read is not a choice. Stacked, each one
  // is a full-width row — which is also the right shape for a chooser, where
  // the options are destinations rather than yes and no.
  //
  // Decided from the count rather than from a prop: a caller who passes three
  // actions has already decided this, and a `stacked` flag would only allow the
  // combination that does not work.
  const stacked = buttons.length > 2;

  // In a row, the last one is primary unless somebody said otherwise: the
  // rightmost button is where a thumb goes and the affirmative belongs there.
  //
  // **Stacked, that rule is wrong and is not applied.** A chooser's last row is
  // normally "Cancel", and filling it would make the way out look like the
  // thing to do. Nothing is filled unless the caller says which — the order
  // stays exactly as it was passed, because in a list the order *is* the
  // meaning.
  const primaryIndex = buttons.some(a => a.primary)
    ? buttons.findIndex(a => a.primary)
    : stacked
      ? -1
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

      <View
        style={[
          stacked ? styles.actionsStacked : styles.actions,
          { gap: space.sm, marginTop: space.xs },
        ]}
      >
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
                stacked && styles.buttonStacked,
                {
                  paddingHorizontal: space.lg,
                  borderRadius: radius.md,
                  backgroundColor: isPrimary ? accent : t.fillSoft,
                  gap: space.sm,
                },
              ]}
            >
              {stacked && action.icon ? (
                <Ionicons
                  name={action.icon}
                  size={18}
                  color={isPrimary ? t.onBrand : t.textSoft}
                />
              ) : null}
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
  actionsStacked: { flexDirection: 'column' },
  // 44, because this is the only tap target on the screen while it is open.
  button: { minHeight: 44, alignItems: 'center', justifyContent: 'center' },
  // Full width, and the content centred rather than left-aligned so a stack of
  // three reads as three buttons and not as a menu that happens to be tappable.
  buttonStacked: { flexDirection: 'row', alignSelf: 'stretch' },
});

export default Dialog;
