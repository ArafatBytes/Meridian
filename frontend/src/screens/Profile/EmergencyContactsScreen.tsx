import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  TextInput,
  ActivityIndicator,
  Platform,
  ScrollView,
  TouchableWithoutFeedback,
  Keyboard,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
// `expo-contacts/legacy`, not `expo-contacts`.
//
// SDK 57 moved expo-contacts to a class-based API and deprecated the old
// function API with a hard throw:
//   "Method presentContactPickerAsync imported from expo-contacts is
//    deprecated. Use the new class-based API or import the legacy API from
//    expo-contacts/legacy."
//
// The new API has no contact picker at all -- it exposes Contact/Container/
// Group classes plus permissions, and the only picker-like thing is
// <ContactAccessButton>, which is iOS 18+ only and a different interaction
// (a button that surfaces contacts matching a query). There is no cross-platform
// replacement for presentContactPickerAsync yet, so the legacy entry point is
// the correct target rather than a workaround.
//
// This will need revisiting when the legacy module is removed. The screen's
// manual-entry modal already covers the same need, so the fallback is a UX
// regression, not a broken feature.
import * as Contacts from 'expo-contacts/legacy';
import { NativeStackNavigationProp } from '@react-navigation/native-stack';
import Dialog from '../../components/Dialog';
import { useDialog } from '../../components/useDialog';
import { useTheme } from '../../theme/ThemeProvider';
import { useStyles } from '../../theme/useStyles';
import type { Palette } from '../../theme/palette';
import { glassBar, glassSurface, lift } from '../../theme/surfaces';
import { Aurora, Sheet } from '../../components/motion';
import { fontFamily, radius, space, type } from '../../theme/type';
import { useAuthStore } from '../../store';
import { supabase } from '../../lib/supabase';
import { EmergencyContact } from '../../types';
import { ProfileStackParamList } from '../../types';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

type EmergencyContactsScreenNavigationProp = NativeStackNavigationProp<
  ProfileStackParamList,
  'EmergencyContacts'
>;

interface Props {
  navigation: EmergencyContactsScreenNavigationProp;
}

const EmergencyContactsScreen: React.FC<Props> = ({ navigation }) => {
  const { t } = useTheme();
  const styles = useStyles(makeStyles);
  const { user } = useAuthStore();
  const insets = useSafeAreaInsets();
  const [contacts, setContacts] = useState<EmergencyContact[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [contactName, setContactName] = useState('');
  const [contactPhone, setContactPhone] = useState('');
  const [contactEmail, setContactEmail] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    fetchEmergencyContacts();
  }, []);

  const dialog = useDialog();

  const fetchEmergencyContacts = async () => {
    try {
      setIsLoading(true);
      const { data, error } = await supabase
        .from('emergency_contacts')
        .select('*')
        .eq('user_id', user?.id)
        .order('created_at', { ascending: false });

      if (error) throw error;
      setContacts(data || []);
    } catch (error: any) {
      dialog.show({
        title: 'Could not load your contacts',
        message: 'The server did not answer. Check your connection and try again.',
        tone: 'danger',
        icon: 'cloud-offline',
      });
      console.error('Error fetching emergency contacts:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const requestContactsPermission = async () => {
    const { status } = await Contacts.requestPermissionsAsync();
    return status === 'granted';
  };

  const pickContactFromDevice = async () => {
    try {
      const hasPermission = await requestContactsPermission();
      if (!hasPermission) {
        dialog.show({
          title: 'Contacts access needed',
          message: 'Meridian needs your contacts to pick one from the phone. You can also type one in.',
          tone: 'warn',
          icon: 'people-outline',
        });
        return;
      }

      const result = await Contacts.presentContactPickerAsync();

      if (result && result.id) {
        const contact = await Contacts.getContactByIdAsync(result.id);

        if (contact) {
          const phoneNumber = contact.phoneNumbers?.[0]?.number;

          // Get contact name - try multiple properties
          let name = 'Unknown';
          if (contact.name) {
            name = contact.name;
          } else if (contact.firstName || contact.lastName) {
            const firstName = contact.firstName || '';
            const lastName = contact.lastName || '';
            name = `${firstName} ${lastName}`.trim();
          } else if (contact.middleName) {
            name = contact.middleName;
          }

          if (!phoneNumber) {
            dialog.show({
              title: 'That contact has no phone number',
              message: 'Pick another, or type the number in yourself.',
              tone: 'warn',
              icon: 'call-outline',
            });
            return;
          }

          // Clean phone number
          const cleanedPhone = phoneNumber.replace(/\D/g, '');
          const email = contact.emails?.[0]?.email || '';

          // Validate phone number
          if (cleanedPhone.length < 10) {
            dialog.show({
              title: 'That number does not look right',
              message: 'A Bangladeshi mobile number is 11 digits, starting 01.',
              tone: 'warn',
              icon: 'call-outline',
            });
            return;
          }

          // Validate email
          if (!email || !email.includes('@')) {
            dialog.show({
              title: 'That contact has no email address',
              message: 'Meridian emails your contacts, so it needs one. Pick another, or type it in.',
              tone: 'warn',
              icon: 'mail-outline',
            });
            return;
          }

          await addEmergencyContact(name, cleanedPhone, email);
        }
      }
    } catch (error: any) {
      dialog.show({
        title: 'Could not read that contact',
        message: 'Something went wrong reading it from your phone. Try typing it in.',
        tone: 'danger',
        icon: 'people-outline',
      });
      console.error('Error picking contact:', error);
    }
  };

  const openManualAddModal = () => {
    setContactName('');
    setContactPhone('');
    setContactEmail('');
    setIsModalVisible(true);
  };

  const handleManualAdd = async () => {
    if (!contactName.trim()) {
      dialog.show({
        title: 'Add a name',
        message: 'Who is this person?',
        tone: 'warn',
        icon: 'person-outline',
      });
      return;
    }

    if (!contactPhone.trim()) {
      dialog.show({
        title: 'Add a phone number',
        message: 'So you can call them.',
        tone: 'warn',
        icon: 'call-outline',
      });
      return;
    }

    const phoneDigits = contactPhone.replace(/\D/g, '');

    if (phoneDigits.length !== 11) {
      dialog.show({
        title: 'That number does not look right',
        message: 'A Bangladeshi mobile number is 11 digits, starting 01.',
        tone: 'warn',
        icon: 'call-outline',
      });
      return;
    }

    if (!contactEmail.trim()) {
      dialog.show({
        title: 'Add an email address',
        message: 'This is where Meridian sends their alert, so it is the one field that has to work.',
        tone: 'warn',
        icon: 'mail-outline',
      });
      return;
    }

    if (!contactEmail.includes('@')) {
      dialog.show({
        title: 'That email does not look right',
        message: 'Check it carefully — an alert sent to the wrong address goes nowhere.',
        tone: 'warn',
        icon: 'mail-outline',
      });
      return;
    }

    await addEmergencyContact(contactName.trim(), phoneDigits, contactEmail.trim());
  };

  const addEmergencyContact = async (name: string, phone: string, email: string) => {
    try {
      setIsSaving(true);

      // Check if contact already exists
      const existingContact = contacts.find(c => c.phone === phone);

      if (existingContact) {
        dialog.show({
          title: 'They are already a contact',
          message: 'This number is already on your list.',
          tone: 'warn',
          icon: 'people-outline',
        });
        setIsModalVisible(false);
        return;
      }

      const { error } = await supabase.from('emergency_contacts').insert({
        user_id: user?.id,
        name,
        phone,
        email,
      });

      if (error) throw error;

      setIsModalVisible(false);
      fetchEmergencyContacts();
    } catch (error: any) {
      dialog.show({
        title: 'Could not add that contact',
        message: 'The server did not answer. Your contacts are unchanged.',
        tone: 'danger',
        icon: 'cloud-offline',
      });
      console.error('Error adding emergency contact:', error);
    } finally {
      setIsSaving(false);
    }
  };

  const deleteEmergencyContact = (contact: EmergencyContact) => {
    dialog.show({
      title: `Remove ${contact.name}?`,
      // Names the consequence, because this list is what an SOS actually
      // sends to. Somebody removing their last contact should know the
      // button stops reaching anybody.
      message: 'They will no longer be told when you raise an SOS or go quiet on a journey.',
      tone: 'danger',
      icon: 'person-remove-outline',
      actions: [
        { label: 'Keep them' },
        {
          label: 'Remove',
          primary: true,
          onPress: async () => {
            try {
              const { error } = await supabase
                .from('emergency_contacts')
                .delete()
                .eq('id', contact.id);

              if (error) throw error;

              fetchEmergencyContacts();
            } catch (error: any) {
              dialog.show({
                title: 'Could not remove them',
                message: 'The server did not answer. They are still on your list.',
                tone: 'danger',
                icon: 'cloud-offline',
              });
              console.error('Error deleting emergency contact:', error);
            }
          },
        },
      ],
    });
  };

  const renderEmptyState = () => (
    <View style={styles.emptyState}>
      <Ionicons name="people-outline" size={80} color={t.textSoft} />
      <Text style={styles.emptyStateTitle}>No Emergency Contacts</Text>
      <Text style={styles.emptyStateText}>
        Add contacts who can be notified in case of an emergency
      </Text>
    </View>
  );

  const renderContactItem = ({ item }: { item: EmergencyContact }) => (
    <View style={styles.contactItem}>
      <View style={styles.contactAvatar}>
        <Ionicons name="person" size={24} color={t.onBrand} />
      </View>
      <View style={styles.contactInfo}>
        <Text style={styles.contactName}>{item.name}</Text>
        <Text style={styles.contactPhone}>{item.phone}</Text>
        <Text style={styles.contactEmail}>{item.email}</Text>
      </View>
      <TouchableOpacity
        style={styles.deleteButton}
        onPress={() => deleteEmergencyContact(item)}
      >
        <Ionicons name="trash-outline" size={24} color={t.danger} />
      </TouchableOpacity>
    </View>
  );

  if (isLoading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color={t.brand} />
      </View>
    );
  }

  return (
    <View style={styles.container}>
      {/* The ambient field, behind everything. `glassSurface` is a
          translucent fill and needs something to be translucent over —
          see the note in theme/surfaces.ts. */}
      <Aurora intensity="ambient" />
      {/* Header */}
      <View style={[styles.header, { paddingTop: insets.top + space.lg }]}>
        <TouchableOpacity
          style={styles.backButton}
          onPress={() => navigation.goBack()}
        >
          <Ionicons name="arrow-back" size={24} color={t.text} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Emergency Contacts</Text>
        <View style={styles.placeholder} />
      </View>

      {/* Contact List */}
      <FlatList
        data={contacts}
        renderItem={renderContactItem}
        keyExtractor={item => item.id}
        contentContainerStyle={[
          styles.listContent,
          contacts.length === 0 && styles.listContentEmpty,
        ]}
        ListEmptyComponent={renderEmptyState}
      />

      {/* Add Buttons.
          `insets.bottom` because this bar is flush with the screen edge and
          the phone's gesture strip lives there: without it the buttons are
          half under the home indicator and the bottom of their labels is
          clipped. The tab bar is not a factor -- this is a pushed screen, and
          the bar slides away on those. */}
      <View style={[styles.buttonContainer, { paddingBottom: insets.bottom + space.sm }]}>
        <TouchableOpacity
          style={styles.addButton}
          onPress={pickContactFromDevice}
        >
          <Ionicons
            name="phone-portrait-outline"
            size={20}
            color={t.onBrand}
          />
          <Text style={styles.addButtonText}>From Contacts</Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.addButton, styles.manualButton]}
          onPress={openManualAddModal}
        >
          <Ionicons name="create-outline" size={20} color={t.onBrand} />
          <Text style={styles.addButtonText}>Add Manually</Text>
        </TouchableOpacity>
      </View>

      {/* Manual Add Modal.
          `avoidKeyboard` because it is a form; not `dismissable`, because a
          stray tap on the scrim would throw away a half-typed contact. */}
      <Sheet
        visible={isModalVisible}
        variant="bottom"
        onClose={() => setIsModalVisible(false)}
        avoidKeyboard
        padding={0}
      >
          <TouchableWithoutFeedback onPress={Keyboard.dismiss}>
              <View style={styles.modalContent}>
                <View style={styles.modalHeader}>
                  <Text style={styles.modalTitle}>Add Emergency Contact</Text>
                  <TouchableOpacity onPress={() => setIsModalVisible(false)}>
                    <Ionicons name="close" size={24} color={t.text} />
                  </TouchableOpacity>
                </View>

                <ScrollView showsVerticalScrollIndicator={false}>
                  <View style={styles.inputContainer}>
                    <Text style={styles.inputLabel}>Name</Text>
                    <TextInput
                      style={styles.input}
                      placeholder="Enter contact name"
                      placeholderTextColor={t.textSoft}
                      value={contactName}
                      onChangeText={setContactName}
                    />
                  </View>

                  <View style={styles.inputContainer}>
                    <Text style={styles.inputLabel}>Phone Number</Text>
                    <TextInput
                      style={styles.input}
                      placeholder="01XXXXXXXXX"
                      placeholderTextColor={t.textSoft}
                      value={contactPhone}
                      onChangeText={setContactPhone}
                      keyboardType="phone-pad"
                      maxLength={11}
                    />
                    <Text style={styles.inputHint}>
                      Enter 11-digit Bangladeshi phone number
                    </Text>
                  </View>

                  <View style={styles.inputContainer}>
                    <Text style={styles.inputLabel}>Email</Text>
                    <TextInput
                      style={styles.input}
                      placeholder="Enter email address"
                      placeholderTextColor={t.textSoft}
                      value={contactEmail}
                      onChangeText={setContactEmail}
                      keyboardType="email-address"
                      autoCapitalize="none"
                    />
                  </View>

                  <TouchableOpacity
                    style={[
                      styles.saveButton,
                      isSaving && styles.saveButtonDisabled,
                    ]}
                    onPress={handleManualAdd}
                    disabled={isSaving}
                  >
                    {isSaving ? (
                      <ActivityIndicator color={t.onBrand} />
                    ) : (
                      <Text style={styles.saveButtonText}>Add Contact</Text>
                    )}
                  </TouchableOpacity>
                </ScrollView>
              </View>
          </TouchableWithoutFeedback>
      </Sheet>

      <Dialog {...dialog.props} />
    </View>
  );
};

const makeStyles = (t: Palette) =>
StyleSheet.create({
    container: {
      flex: 1,
      backgroundColor: t.bg,
    },
    loadingContainer: {
      flex: 1,
      justifyContent: 'center',
      alignItems: 'center',
      backgroundColor: t.bg,
    },
    header: {
      ...glassBar(t),
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'space-between',
      paddingHorizontal: space.xl,
      paddingBottom: space.lg,
    },
    backButton: {
      padding: space.sm,
    },
    headerTitle: {
      ...type.heading,
      color: t.text,
    },
    placeholder: {
      width: 40,
    },
    listContent: {
      padding: space.xl,
    },
    listContentEmpty: {
      flex: 1,
    },
    emptyState: {
      flex: 1,
      justifyContent: 'center',
      alignItems: 'center',
      paddingHorizontal: space.xxl,
    },
    emptyStateTitle: {
      ...type.heading,
      color: t.text,
      marginTop: space.xl,
      marginBottom: space.sm,
    },
    emptyStateText: {
      ...type.body,
      color: t.textSoft,
      textAlign: 'center',
    },
    contactItem: {
      ...glassSurface(t),
      flexDirection: 'row',
      alignItems: 'center',
      padding: space.xl,
      marginBottom: space.lg,
      ...lift(t, 1),
    },
    contactAvatar: {
      width: 50,
      height: 50,
      borderRadius: 25,
      backgroundColor: t.brand,
      justifyContent: 'center',
      alignItems: 'center',
    },
    contactInfo: {
      flex: 1,
      marginLeft: space.lg,
    },
    contactName: {
      ...type.bodyStrong,
      color: t.text,
      marginBottom: space.xs,
    },
    contactPhone: {
      ...type.body,
      color: t.textSoft,
      marginBottom: 2,
    },
    contactEmail: {
      ...type.small,
      color: t.textSoft,
    },
    deleteButton: {
      padding: space.sm,
    },
    buttonContainer: {
      ...glassSurface(t),
      flexDirection: 'row',
      paddingHorizontal: space.xl,
      paddingVertical: space.sm,
      borderTopWidth: 1,
      borderTopColor: t.line,
      gap: space.sm,
    },
    addButton: {
      flex: 1,
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'center',
      backgroundColor: t.brand,
      paddingVertical: space.lg,
      paddingHorizontal: space.sm,
      borderRadius: radius.md,
    },
    manualButton: {
      backgroundColor: t.accent,
    },
    addButtonText: {
      ...type.bodyStrong,
      color: t.onBrand,
      marginLeft: space.sm,
    },
    // `Sheet` owns the scrim, the material and the shape. This is the inset,
    // which it cannot own: the ScrollView inside has to reach the pane's edges
    // or its scroll indicator sits in the middle of the padding.
    modalContent: {
      padding: space.xxl,
      paddingBottom: Platform.OS === 'ios' ? space.xxl : space.huge,
    },
    modalHeader: {
      flexDirection: 'row',
      justifyContent: 'space-between',
      alignItems: 'center',
      marginBottom: space.xxl,
    },
    modalTitle: {
      ...type.heading,
      color: t.text,
    },
    inputContainer: {
      marginBottom: space.xl,
    },
    inputLabel: {
      ...type.bodyStrong,
      color: t.text,
      marginBottom: space.sm,
    },
    input: {
      ...type.body,
      backgroundColor: t.bg,
      borderWidth: 1,
      borderColor: t.line,
      borderRadius: radius.md,
      padding: space.lg,
      color: t.text,
    },
    inputHint: {
      ...type.small,
      color: t.textSoft,
      marginTop: space.xs,
    },
    saveButton: {
      backgroundColor: t.brand,
      padding: space.xl,
      borderRadius: radius.md,
      alignItems: 'center',
      marginTop: space.lg,
    },
    saveButtonDisabled: {
      opacity: 0.6,
    },
    saveButtonText: {
      ...type.bodyStrong,
      color: t.onBrand,
    },
  });

export default EmergencyContactsScreen;
