import * as Notifications from 'expo-notifications';
import * as Device from 'expo-device';
import Constants from 'expo-constants';
import { Platform } from 'react-native';
import * as SecureStore from 'expo-secure-store';
import { NOTIFICATION_CHANNELS, STORAGE_KEYS } from '../constants';
import { NotificationData } from '../types';

// Configure notification behavior
Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: true,
    shouldSetBadge: true,
    shouldShowBanner: true,
    shouldShowList: true,
  }),
});

class NotificationService {
  private notificationListener?: Notifications.Subscription;
  private responseListener?: Notifications.Subscription;

  async initialize(): Promise<void> {
    await this.createChannels();
    await this.requestPermission();
    await this.setupNotificationListeners();
    await this.getExpoPushToken();
  }

  private async createChannels(): Promise<void> {
    if (Platform.OS === 'android') {
      await Notifications.setNotificationChannelAsync(
        NOTIFICATION_CHANNELS.DANGER_ZONE,
        {
          name: 'Danger Zone Alerts',
          importance: Notifications.AndroidImportance.HIGH,
          vibrationPattern: [0, 250, 250, 250],
          sound: 'default',
          enableVibrate: true,
        },
      );

      await Notifications.setNotificationChannelAsync(
        NOTIFICATION_CHANNELS.SOS_ALERT,
        {
          name: 'SOS Alerts',
          importance: Notifications.AndroidImportance.MAX,
          vibrationPattern: [0, 300, 500, 300, 500],
          sound: 'sos_alert',
          enableVibrate: true,
        },
      );

      await Notifications.setNotificationChannelAsync(
        NOTIFICATION_CHANNELS.CRIME_REPORT,
        {
          name: 'Crime Reports',
          importance: Notifications.AndroidImportance.DEFAULT,
          sound: 'default',
        },
      );

      await Notifications.setNotificationChannelAsync(
        NOTIFICATION_CHANNELS.SYSTEM,
        {
          name: 'System Notifications',
          importance: Notifications.AndroidImportance.LOW,
        },
      );
    }
  }

  async requestPermission(): Promise<boolean> {
    const { status: existingStatus } =
      await Notifications.getPermissionsAsync();
    let finalStatus = existingStatus;

    if (existingStatus !== 'granted') {
      const { status } = await Notifications.requestPermissionsAsync();
      finalStatus = status;
    }

    return finalStatus === 'granted';
  }

  async getExpoPushToken(): Promise<string | null> {
    try {
      if (!Device.isDevice) {
        console.log('Must use physical device for push notifications');
        return null;
      }

      const token = (
        await Notifications.getExpoPushTokenAsync({
          projectId: Constants.expoConfig?.extra?.eas?.projectId,
        })
      ).data;

      if (token) {
        await SecureStore.setItemAsync(STORAGE_KEYS.FCM_TOKEN, token);
        return token;
      }
      return null;
    } catch (error) {
      console.error('Error getting Expo push token:', error);
      return null;
    }
  }

  async deleteExpoPushToken(): Promise<void> {
    try {
      await SecureStore.deleteItemAsync(STORAGE_KEYS.FCM_TOKEN);
    } catch (error) {
      console.error('Error deleting push token:', error);
    }
  }

  private async setupNotificationListeners(): Promise<void> {
    // Handle notification received while app is foregrounded
    this.notificationListener = Notifications.addNotificationReceivedListener(
      (notification: Notifications.Notification) => {
        console.log('Notification received:', notification);
      },
    );

    // Handle user tapping on notification
    this.responseListener =
      Notifications.addNotificationResponseReceivedListener(
        (response: Notifications.NotificationResponse) => {
          console.log('Notification tapped:', response);
          // Handle navigation based on notification data
          const data = response.notification.request.content.data;
          console.log('Notification data:', data);
        },
      );
  }

  async displayNotification(data: NotificationData): Promise<void> {
    await Notifications.scheduleNotificationAsync({
      content: {
        title: data.title,
        body: data.body,
        data: data.data,
        sound: data.type === 'sos_alert' ? 'sos_alert.wav' : 'default',
        priority:
          data.type === 'sos_alert'
            ? Notifications.AndroidNotificationPriority.MAX
            : Notifications.AndroidNotificationPriority.HIGH,
        vibrate: data.type === 'sos_alert' ? [0, 300, 500, 300, 500] : [0, 250],
        badge: 1,
      },
      trigger: null, // Show immediately
    });
  }

  async displayDangerZoneAlert(
    title: string,
    message: string,
    crimeScore: number,
  ): Promise<void> {
    await Notifications.scheduleNotificationAsync({
      content: {
        title,
        body: message,
        data: { type: 'danger_zone', crimeScore },
        sound: 'danger_alert.wav',
        priority: Notifications.AndroidNotificationPriority.HIGH,
        vibrate: [0, 300, 500],
        color: this.getDangerColor(crimeScore),
        badge: 1,
      },
      trigger: null,
    });
  }

  async displaySOSAlert(userName: string, location: string): Promise<void> {
    await Notifications.scheduleNotificationAsync({
      content: {
        title: '🚨 SOS ALERT',
        body: `${userName} needs emergency help at ${location}`,
        data: { type: 'sos_alert', userName, location },
        sound: 'sos_alert.wav',
        priority: Notifications.AndroidNotificationPriority.MAX,
        vibrate: [0, 300, 500, 300, 500, 300, 500],
        color: '#E53935',
        badge: 1,
        sticky: true,
      },
      trigger: null,
    });
  }

  private getChannelId(type: NotificationData['type']): string {
    switch (type) {
      case 'danger_zone':
        return NOTIFICATION_CHANNELS.DANGER_ZONE;
      case 'sos_alert':
        return NOTIFICATION_CHANNELS.SOS_ALERT;
      case 'crime_report':
        return NOTIFICATION_CHANNELS.CRIME_REPORT;
      case 'system':
      default:
        return NOTIFICATION_CHANNELS.SYSTEM;
    }
  }

  private getDangerColor(crimeScore: number): string {
    if (crimeScore >= 9.0) {
      return '#E53935'; // Critical
    }
    if (crimeScore >= 7.5) {
      return '#FF7043'; // High
    }
    if (crimeScore >= 5.0) {
      return '#FFA726'; // Medium
    }
    return '#66BB6A'; // Low
  }

  async cancelAllNotifications(): Promise<void> {
    await Notifications.cancelAllScheduledNotificationsAsync();
  }

  async cancelNotification(notificationId: string): Promise<void> {
    await Notifications.cancelScheduledNotificationAsync(notificationId);
  }

  cleanup(): void {
    if (this.notificationListener) {
      this.notificationListener.remove();
    }
    if (this.responseListener) {
      this.responseListener.remove();
    }
  }
}

export default new NotificationService();
