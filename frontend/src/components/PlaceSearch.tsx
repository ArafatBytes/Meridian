import React, { useState } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  ActivityIndicator,
  StyleSheet,
  Keyboard,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { spacing, borderRadius, fontSize } from '../theme';
import { useTheme } from '../theme/ThemeProvider';
import { useStyles } from '../theme/useStyles';
import type { Palette } from '../theme/palette';
import { fontFamily } from '../theme/type';
import { geoService } from '../services/geo.service';
import type { GeoResolution, GeoMethod } from '../types/contracts/geo';

/**
 * Bangla place search — demo beat 3.
 *
 * Type "Mirpur 10 golchattar", or মিরপুর ১০ গোলচত্বর, and the map flies there. A
 * chip says how it resolved. Type a place that does not exist and it says so
 * rather than guessing.
 *
 * Two deliberate decisions about what is on screen:
 *
 * **The method chip is a feature, not debug output.** It is the difference
 * between "a map found something" and "our gazetteer knew this, a general map
 * would not". A judge should be able to see which tier answered.
 *
 * **"Could not find that place" is shown proudly.** It is the discard invariant
 * made visible — unresolvable locations are discarded, never guessed — and it is
 * a far better answer to a judge than a pin in a plausible-looking wrong spot.
 * Do not replace it with a silent no-op or a nearest guess.
 *
 * All judgment is server-side. This component renders an answer; it does not
 * second-guess one.
 */

interface PlaceSearchProps {
  /** Called only when a place actually resolved. Never called for `unresolved`. */
  onResolved: (resolution: GeoResolution) => void;
  placeholder?: string;
}

interface ChipStyle {
  label: string;
  colour: string;
  icon: keyof typeof Ionicons.glyphMap;
}

/**
 * How each resolution method is presented.
 *
 * `gazetteer` reads as certain because it is: a hand-reviewed entry with real
 * coordinates. `llm_gazetteer` reads as provisional on purpose — it is a model's
 * answer that passed a bounding-box check, which is weaker, and the interface
 * should not flatten that difference.
 */
const methodChip = (
  t: Palette,
): Record<Exclude<GeoMethod, 'unresolved'>, ChipStyle> => ({
  gazetteer: { label: 'From our Dhaka gazetteer', colour: t.ok, icon: 'book-outline' },
  llm_gazetteer: { label: 'Inferred by AI', colour: t.info, icon: 'sparkles-outline' },
  nominatim: { label: 'From a map service', colour: t.info, icon: 'globe-outline' },
});

export default function PlaceSearch({ onResolved, placeholder }: PlaceSearchProps) {
  const { t } = useTheme();
  const styles = useStyles(makeStyles);
  const [query, setQuery] = useState('');
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<GeoResolution | null>(null);
  const [failedQuery, setFailedQuery] = useState<string | null>(null);

  const submit = async () => {
    const text = query.trim();
    if (!text || busy) {
      return;
    }
    Keyboard.dismiss();
    setBusy(true);
    setResult(null);
    setFailedQuery(null);

    const answer = await geoService.resolve(text);

    // The box may have moved on while the request was in flight. Showing a stale
    // answer against a newer query is worse than showing none.
    if (answer.query.trim() !== text) {
      setBusy(false);
      return;
    }

    if (answer.resolution.method === 'unresolved') {
      setFailedQuery(text);
    } else {
      setResult(answer.resolution);
      onResolved(answer.resolution);
    }
    setBusy(false);
  };

  const clear = () => {
    setQuery('');
    setResult(null);
    setFailedQuery(null);
  };

  const chip = result && result.method !== 'unresolved' ? methodChip(t)[result.method] : null;

  return (
    <View style={styles.container}>
      <View style={styles.inputRow}>
        <Ionicons name="search" size={18} color={t.textFaint} />
        <TextInput
          style={styles.input}
          value={query}
          onChangeText={setQuery}
          onSubmitEditing={submit}
          placeholder={placeholder ?? 'Mirpur 10 golchattar'}
          placeholderTextColor={t.textFaint}
          returnKeyType="search"
          autoCorrect={false}
          autoCapitalize="none"
        />
        {busy ? (
          <ActivityIndicator size="small" color={t.textSoft} />
        ) : query.length > 0 ? (
          <TouchableOpacity onPress={clear} hitSlop={8}>
            <Ionicons name="close-circle" size={18} color={t.textFaint} />
          </TouchableOpacity>
        ) : null}
      </View>

      {chip && result && (
        <View style={styles.resultRow}>
          <Text style={styles.resolvedName} numberOfLines={1}>
            {result.resolvedName}
          </Text>
          <View style={[styles.chip, { borderColor: chip.colour }]}>
            <Ionicons name={chip.icon} size={11} color={chip.colour} />
            <Text style={[styles.chipText, { color: chip.colour }]}>{chip.label}</Text>
          </View>
        </View>
      )}

      {failedQuery && (
        <View style={styles.failRow}>
          <Ionicons name="help-circle-outline" size={15} color={t.textSoft} />
          <Text style={styles.failText}>
            Could not find “{failedQuery}”. We will not guess a location.
          </Text>
        </View>
      )}
    </View>
  );
}

const makeStyles = (t: Palette) =>
StyleSheet.create({
    container: {
      backgroundColor: t.surface,
      borderRadius: borderRadius.xl,
      paddingHorizontal: spacing.md,
      paddingVertical: spacing.sm,
      shadowColor: '#000',
      shadowOpacity: 0.15,
      shadowRadius: 6,
      shadowOffset: { width: 0, height: 2 },
      elevation: 4,
    },
    inputRow: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: spacing.sm,
    },
    input: {
      fontFamily: fontFamily.body,
      flex: 1,
      paddingVertical: spacing.xs,
      fontSize: fontSize.sm,
      color: t.text,
    },
    resultRow: {
      marginTop: spacing.sm,
      paddingTop: spacing.sm,
      borderTopWidth: StyleSheet.hairlineWidth,
      borderTopColor: t.line,
      gap: spacing.xs,
    },
    resolvedName: {
      fontFamily: fontFamily.bodySemi,
      fontSize: fontSize.sm,
      color: t.text,
    },
    chip: {
      alignSelf: 'flex-start',
      flexDirection: 'row',
      alignItems: 'center',
      gap: 4,
      borderWidth: 1,
      borderRadius: borderRadius.full,
      paddingHorizontal: spacing.sm,
      paddingVertical: 2,
    },
    chipText: {
      fontFamily: fontFamily.bodySemi,
      fontSize: fontSize.xs,
    },
    failRow: {
      marginTop: spacing.sm,
      paddingTop: spacing.sm,
      borderTopWidth: StyleSheet.hairlineWidth,
      borderTopColor: t.line,
      flexDirection: 'row',
      alignItems: 'center',
      gap: spacing.xs,
    },
    failText: {
      fontFamily: fontFamily.body,
      flex: 1,
      fontSize: fontSize.xs,
      color: t.textSoft,
    },
  });
