import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  Alert,
  TextInput,
  Modal,
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  TouchableWithoutFeedback,
  Keyboard,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import * as Contacts from 'expo-contacts';
import { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { colors, spacing, borderRadius, fontSize } from '../../theme';
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
      Alert.alert('Error', 'Failed to load emergency contacts');
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
        Alert.alert(
          'Permission Required',
          'Please grant contacts permission to add contacts from your device',
        );
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
            Alert.alert('Error', 'Selected contact has no phone number');
            return;
          }

          // Clean phone number
          const cleanedPhone = phoneNumber.replace(/\D/g, '');
          const email = contact.emails?.[0]?.email || '';

          // Validate phone number
          if (cleanedPhone.length < 10) {
            Alert.alert('Error', 'Invalid phone number');
            return;
          }

          // Validate email
          if (!email || !email.includes('@')) {
            Alert.alert('Error', 'Selected contact must have a valid email address');
            return;
          }

          await addEmergencyContact(name, cleanedPhone, email);
        }
      }
    } catch (error: any) {
      Alert.alert('Error', 'Failed to pick contact');
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
      Alert.alert('Error', 'Please enter contact name');
      return;
    }

    if (!contactPhone.trim()) {
      Alert.alert('Error', 'Please enter phone number');
      return;
    }

    const phoneDigits = contactPhone.replace(/\D/g, '');

    if (phoneDigits.length !== 11) {
      Alert.alert('Error', 'Phone number must be exactly 11 digits');
      return;
    }

    if (!contactEmail.trim()) {
      Alert.alert('Error', 'Please enter email address');
      return;
    }

    if (!contactEmail.includes('@')) {
      Alert.alert('Error', 'Please enter a valid email address');
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
        Alert.alert(
          'Error',
          'This contact is already in your emergency contacts',
        );
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

      Alert.alert('Success', 'Emergency contact added successfully');
      setIsModalVisible(false);
      fetchEmergencyContacts();
    } catch (error: any) {
      Alert.alert('Error', 'Failed to add emergency contact');
      console.error('Error adding emergency contact:', error);
    } finally {
      setIsSaving(false);
    }
  };

  const deleteEmergencyContact = (contact: EmergencyContact) => {
    Alert.alert(
      'Delete Contact',
      `Are you sure you want to remove ${contact.name} from emergency contacts?`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete',
          style: 'destructive',
          onPress: async () => {
            try {
              const { error } = await supabase
                .from('emergency_contacts')
                .delete()
                .eq('id', contact.id);

              if (error) throw error;

              Alert.alert('Success', 'Emergency contact removed');
              fetchEmergencyContacts();
            } catch (error: any) {
              Alert.alert('Error', 'Failed to delete emergency contact');
              console.error('Error deleting emergency contact:', error);
            }
          },
        },
      ],
    );
  };

  const renderEmptyState = () => (
    <View style={styles.emptyState}>
      <Ionicons name="people-outline" size={80} color={colors.textSecondary} />
      <Text style={styles.emptyStateTitle}>No Emergency Contacts</Text>
      <Text style={styles.emptyStateText}>
        Add contacts who can be notified in case of an emergency
      </Text>
    </View>
  );

  const renderContactItem = ({ item }: { item: EmergencyContact }) => (
    <View style={styles.contactItem}>
      <View style={styles.contactAvatar}>
        <Ionicons name="person" size={24} color={colors.white} />
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
        <Ionicons name="trash-outline" size={24} color={colors.error} />
      </TouchableOpacity>
    </View>
  );

  if (isLoading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color={colors.primary} />
      </View>
    );
  }

  return (
    <View style={styles.container}>
      {/* Header */}
      <View style={[styles.header, { paddingTop: insets.top + spacing.md }]}>
        <TouchableOpacity
          style={styles.backButton}
          onPress={() => navigation.goBack()}
        >
          <Ionicons name="arrow-back" size={24} color={colors.text} />
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

      {/* Add Buttons */}
      <View style={[styles.buttonContainer]}>
        <TouchableOpacity
          style={styles.addButton}
          onPress={pickContactFromDevice}
        >
          <Ionicons
            name="phone-portrait-outline"
            size={20}
            color={colors.white}
          />
          <Text style={styles.addButtonText}>From Contacts</Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.addButton, styles.manualButton]}
          onPress={openManualAddModal}
        >
          <Ionicons name="create-outline" size={20} color={colors.white} />
          <Text style={styles.addButtonText}>Add Manually</Text>
        </TouchableOpacity>
      </View>

      {/* Manual Add Modal */}
      <Modal
        visible={isModalVisible}
        transparent
        animationType="slide"
        onRequestClose={() => setIsModalVisible(false)}
      >
        <KeyboardAvoidingView
          behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
          style={styles.modalOverlay}
        >
          <TouchableWithoutFeedback onPress={Keyboard.dismiss}>
            <View style={styles.modalOverlay}>
              <View style={styles.modalContent}>
                <View style={styles.modalHeader}>
                  <Text style={styles.modalTitle}>Add Emergency Contact</Text>
                  <TouchableOpacity onPress={() => setIsModalVisible(false)}>
                    <Ionicons name="close" size={24} color={colors.text} />
                  </TouchableOpacity>
                </View>

                <ScrollView showsVerticalScrollIndicator={false}>
                  <View style={styles.inputContainer}>
                    <Text style={styles.inputLabel}>Name</Text>
                    <TextInput
                      style={styles.input}
                      placeholder="Enter contact name"
                      placeholderTextColor={colors.textSecondary}
                      value={contactName}
                      onChangeText={setContactName}
                    />
                  </View>

                  <View style={styles.inputContainer}>
                    <Text style={styles.inputLabel}>Phone Number</Text>
                    <TextInput
                      style={styles.input}
                      placeholder="01XXXXXXXXX"
                      placeholderTextColor={colors.textSecondary}
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
                      placeholderTextColor={colors.textSecondary}
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
                      <ActivityIndicator color={colors.white} />
                    ) : (
                      <Text style={styles.saveButtonText}>Add Contact</Text>
                    )}
                  </TouchableOpacity>
                </ScrollView>
              </View>
            </View>
          </TouchableWithoutFeedback>
        </KeyboardAvoidingView>
      </Modal>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: colors.background,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.md,
    backgroundColor: colors.white,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  backButton: {
    padding: spacing.sm,
  },
  headerTitle: {
    fontSize: fontSize.xl,
    fontWeight: 'bold',
    color: colors.text,
  },
  placeholder: {
    width: 40,
  },
  listContent: {
    padding: spacing.lg,
  },
  listContentEmpty: {
    flex: 1,
  },
  emptyState: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: spacing.xl,
  },
  emptyStateTitle: {
    fontSize: fontSize.xl,
    fontWeight: 'bold',
    color: colors.text,
    marginTop: spacing.lg,
    marginBottom: spacing.sm,
  },
  emptyStateText: {
    fontSize: fontSize.md,
    color: colors.textSecondary,
    textAlign: 'center',
  },
  contactItem: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.white,
    padding: spacing.lg,
    borderRadius: borderRadius.md,
    marginBottom: spacing.md,
    shadowColor: colors.black,
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 2,
  },
  contactAvatar: {
    width: 50,
    height: 50,
    borderRadius: 25,
    backgroundColor: colors.primary,
    justifyContent: 'center',
    alignItems: 'center',
  },
  contactInfo: {
    flex: 1,
    marginLeft: spacing.md,
  },
  contactName: {
    fontSize: fontSize.lg,
    fontWeight: '600',
    color: colors.text,
    marginBottom: spacing.xs,
  },
  contactPhone: {
    fontSize: fontSize.md,
    color: colors.textSecondary,
    marginBottom: 2,
  },
  contactEmail: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
  },
  deleteButton: {
    padding: spacing.sm,
  },
  buttonContainer: {
    flexDirection: 'row',
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
    backgroundColor: colors.white,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    gap: spacing.sm,
  },
  addButton: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.primary,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.sm,
    borderRadius: borderRadius.md,
  },
  manualButton: {
    backgroundColor: colors.secondary,
  },
  addButtonText: {
    fontSize: fontSize.md,
    fontWeight: '600',
    color: colors.white,
    marginLeft: spacing.sm,
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
    justifyContent: 'flex-end',
  },
  modalContent: {
    backgroundColor: colors.white,
    borderTopLeftRadius: borderRadius.xl,
    borderTopRightRadius: borderRadius.xl,
    padding: spacing.xl,
    paddingBottom: Platform.OS === 'ios' ? spacing.xl : spacing.xxl,
    maxHeight: '80%',
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.xl,
  },
  modalTitle: {
    fontSize: fontSize.xl,
    fontWeight: 'bold',
    color: colors.text,
  },
  inputContainer: {
    marginBottom: spacing.lg,
  },
  inputLabel: {
    fontSize: fontSize.md,
    fontWeight: '600',
    color: colors.text,
    marginBottom: spacing.sm,
  },
  input: {
    backgroundColor: colors.background,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: borderRadius.md,
    padding: spacing.md,
    fontSize: fontSize.md,
    color: colors.text,
  },
  inputHint: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    marginTop: spacing.xs,
  },
  saveButton: {
    backgroundColor: colors.primary,
    padding: spacing.lg,
    borderRadius: borderRadius.md,
    alignItems: 'center',
    marginTop: spacing.md,
  },
  saveButtonDisabled: {
    opacity: 0.6,
  },
  saveButtonText: {
    fontSize: fontSize.lg,
    fontWeight: '600',
    color: colors.white,
  },
});

export default EmergencyContactsScreen;
