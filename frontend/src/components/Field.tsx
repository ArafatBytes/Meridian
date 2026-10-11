/**
 * `Field` — a labelled text input, themed, with an error slot.
 *
 * Extracted because Login and Register together have seven of these and the
 * styling is non-trivial: the border has to switch to `danger` on error, the
 * placeholder has to be `textFaint` (RN does not inherit it), and a password
 * field needs a reveal button inset over the text with the padding to match.
 * Written twice, those drift — and the one that drifts is always the error
 * state, because it is the one you do not look at while building.
 *
 * ## The error does not displace the field
 *
 * The message renders in a row of fixed minimum height below the input, so the
 * form does not jump when validation fails. On a five-field form, validating
 * all of them at once with growing rows moves every field under the user's
 * finger at the moment they are reading what went wrong.
 *
 * ## Why the reveal button exists
 *
 * Both screens enforce an 8-character minimum and Register asks for the
 * password twice. Without a way to see what you typed, a single mistyped
 * character means "Passwords do not match" with no way to find out why. It
 * defaults to hidden and is per-field.
 */

import React, { useState } from 'react';
import {
  View,
  Text,
  TextInput,
  Pressable,
  StyleSheet,
  type TextInputProps,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { useTheme } from '../theme/ThemeProvider';

export interface FieldProps extends Omit<TextInputProps, 'style'> {
  label: string;
  /** Validation message. Empty or undefined renders the reserved space only. */
  error?: string;
  /** Renders as a password field with a reveal toggle. */
  secure?: boolean;
}

export const Field: React.FC<FieldProps> = ({ label, error, secure, ...input }) => {
  const { t, type, space, radius } = useTheme();
  const [visible, setVisible] = useState(false);

  return (
    <View style={{ marginBottom: space.md }}>
      <Text style={[type.label, { color: t.textSoft, marginBottom: space.sm }]}>
        {label}
      </Text>

      <View style={styles.row}>
        <TextInput
          {...input}
          style={[
            type.body,
            styles.input,
            {
              backgroundColor: t.surface,
              borderColor: error ? t.danger : t.line,
              borderRadius: radius.md,
              padding: space.md,
              color: t.text,
              // Clear of the reveal button, so long input does not slide under it.
              paddingRight: secure ? 46 : space.md,
            },
          ]}
          placeholderTextColor={t.textFaint}
          secureTextEntry={secure ? !visible : false}
        />
        {secure ? (
          <Pressable
            onPress={() => setVisible(current => !current)}
            hitSlop={10}
            style={styles.reveal}
            accessibilityRole="button"
            accessibilityLabel={visible ? 'Hide password' : 'Show password'}
          >
            <Ionicons
              name={visible ? 'eye-off-outline' : 'eye-outline'}
              size={20}
              color={t.textFaint}
            />
          </Pressable>
        ) : null}
      </View>

      {/* Always rendered, so the layout does not shift when a message appears. */}
      <View style={styles.errorSlot}>
        {error ? <Text style={[type.caption, { color: t.danger }]}>{error}</Text> : null}
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  row: { justifyContent: 'center' },
  input: { borderWidth: StyleSheet.hairlineWidth * 2 },
  reveal: { position: 'absolute', right: 12, padding: 4 },
  errorSlot: { minHeight: 17, justifyContent: 'center' },
});

export default Field;
