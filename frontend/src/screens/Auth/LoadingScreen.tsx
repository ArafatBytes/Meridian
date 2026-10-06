import React, { useEffect, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  Animated,
  Easing,
  Dimensions,
} from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { Ionicons, MaterialCommunityIcons } from '@expo/vector-icons';
import { colors, spacing, fontSize } from '../../theme';

// @ts-ignore - LinearGradient type compatibility
const GradientView = LinearGradient as any;

const { width, height } = Dimensions.get('window');

const LoadingScreen: React.FC = () => {
  const fadeAnim = useRef(new Animated.Value(0)).current;
  const scaleAnim = useRef(new Animated.Value(0.3)).current;
  const rotateAnim = useRef(new Animated.Value(0)).current;
  const pulseAnim = useRef(new Animated.Value(1)).current;
  const slideAnim = useRef(new Animated.Value(50)).current;

  useEffect(() => {
    // Fade in and scale animation
    Animated.parallel([
      Animated.timing(fadeAnim, {
        toValue: 1,
        duration: 800,
        useNativeDriver: true,
        easing: Easing.out(Easing.ease),
      }),
      Animated.spring(scaleAnim, {
        toValue: 1,
        friction: 4,
        tension: 40,
        useNativeDriver: true,
      }),
      Animated.timing(slideAnim, {
        toValue: 0,
        duration: 800,
        useNativeDriver: true,
        easing: Easing.out(Easing.ease),
      }),
    ]).start();

    // Continuous rotation animation
    Animated.loop(
      Animated.timing(rotateAnim, {
        toValue: 1,
        duration: 2000,
        useNativeDriver: true,
        easing: Easing.linear,
      }),
    ).start();

    // Pulse animation
    Animated.loop(
      Animated.sequence([
        Animated.timing(pulseAnim, {
          toValue: 1.2,
          duration: 1000,
          useNativeDriver: true,
          easing: Easing.inOut(Easing.ease),
        }),
        Animated.timing(pulseAnim, {
          toValue: 1,
          duration: 1000,
          useNativeDriver: true,
          easing: Easing.inOut(Easing.ease),
        }),
      ]),
    ).start();
  }, [fadeAnim, scaleAnim, rotateAnim, pulseAnim, slideAnim]);

  const spin = rotateAnim.interpolate({
    inputRange: [0, 1],
    outputRange: ['0deg', '360deg'],
  });

  return (
    <GradientView
      colors={[colors.primary, colors.secondary, colors.primary]}
      style={styles.container}
      start={{ x: 0, y: 0 }}
      end={{ x: 1, y: 1 }}
    >
      <Animated.View
        style={[
          styles.content,
          {
            opacity: fadeAnim,
            transform: [{ scale: scaleAnim }],
          },
        ]}
      >
        {/* Rotating outer ring */}
        <Animated.View
          style={[
            styles.outerRing,
            {
              transform: [{ rotate: spin }],
            },
          ]}
        >
          <View style={styles.ring} />
        </Animated.View>

        {/* Pulsing shield icon */}
        <Animated.View
          style={[
            styles.iconContainer,
            {
              transform: [{ scale: pulseAnim }],
            },
          ]}
        >
          <MaterialCommunityIcons
            name="shield-check"
            size={80}
            color={colors.white}
          />
        </Animated.View>

        {/* Security indicators around the icon */}
        <View style={styles.indicatorsContainer}>
          <Animated.View
            style={[styles.indicator, styles.indicator1, { opacity: fadeAnim }]}
          >
            <Ionicons name="location" size={24} color={colors.white} />
          </Animated.View>
          <Animated.View
            style={[styles.indicator, styles.indicator2, { opacity: fadeAnim }]}
          >
            <Ionicons name="people" size={24} color={colors.white} />
          </Animated.View>
          <Animated.View
            style={[styles.indicator, styles.indicator3, { opacity: fadeAnim }]}
          >
            <Ionicons name="warning" size={24} color={colors.white} />
          </Animated.View>
          <Animated.View
            style={[styles.indicator, styles.indicator4, { opacity: fadeAnim }]}
          >
            <MaterialCommunityIcons
              name="map-marker-alert"
              size={24}
              color={colors.white}
            />
          </Animated.View>
        </View>

        {/* Text content */}
        <Animated.View
          style={[
            styles.textContainer,
            {
              opacity: fadeAnim,
              transform: [{ translateY: slideAnim }],
            },
          ]}
        >
          <Text style={styles.title}>Meridian</Text>
          <Text style={styles.subtitle}>Setting up your safety zone...</Text>

          {/* Loading dots */}
          <View style={styles.dotsContainer}>
            <Animated.View
              style={[
                styles.dot,
                {
                  opacity: pulseAnim,
                },
              ]}
            />
            <Animated.View
              style={[
                styles.dot,
                {
                  opacity: pulseAnim,
                },
              ]}
            />
            <Animated.View
              style={[
                styles.dot,
                {
                  opacity: pulseAnim,
                },
              ]}
            />
          </View>
        </Animated.View>
      </Animated.View>

      {/* Decorative elements */}
      <Animated.View
        style={[styles.floatingCircle, styles.circle1, { opacity: fadeAnim }]}
      />
      <Animated.View
        style={[styles.floatingCircle, styles.circle2, { opacity: fadeAnim }]}
      />
      <Animated.View
        style={[styles.floatingCircle, styles.circle3, { opacity: fadeAnim }]}
      />
    </GradientView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  content: {
    alignItems: 'center',
    justifyContent: 'center',
  },
  outerRing: {
    position: 'absolute',
    width: 200,
    height: 200,
    justifyContent: 'center',
    alignItems: 'center',
  },
  ring: {
    width: 200,
    height: 200,
    borderRadius: 100,
    borderWidth: 3,
    borderColor: colors.white,
    borderStyle: 'dashed',
    opacity: 0.3,
  },
  iconContainer: {
    width: 120,
    height: 120,
    borderRadius: 60,
    backgroundColor: 'rgba(255, 255, 255, 0.2)',
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: spacing.xl,
  },
  indicatorsContainer: {
    position: 'absolute',
    width: 280,
    height: 280,
  },
  indicator: {
    position: 'absolute',
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: 'rgba(255, 255, 255, 0.2)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  indicator1: {
    top: 0,
    left: '50%',
    marginLeft: -24,
  },
  indicator2: {
    right: 0,
    top: '50%',
    marginTop: -24,
  },
  indicator3: {
    bottom: 0,
    left: '50%',
    marginLeft: -24,
  },
  indicator4: {
    left: 0,
    top: '50%',
    marginTop: -24,
  },
  textContainer: {
    alignItems: 'center',
    marginTop: spacing.xl * 2,
  },
  title: {
    fontSize: 32,
    fontWeight: 'bold',
    color: colors.white,
    marginBottom: spacing.sm,
    textShadowColor: 'rgba(0, 0, 0, 0.3)',
    textShadowOffset: { width: 0, height: 2 },
    textShadowRadius: 4,
  },
  subtitle: {
    fontSize: fontSize.md,
    color: colors.white,
    marginBottom: spacing.lg,
    textAlign: 'center',
    opacity: 0.9,
  },
  dotsContainer: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    marginTop: spacing.md,
  },
  dot: {
    width: 10,
    height: 10,
    borderRadius: 5,
    backgroundColor: colors.white,
    marginHorizontal: 6,
  },
  floatingCircle: {
    position: 'absolute',
    borderRadius: 1000,
    backgroundColor: 'rgba(255, 255, 255, 0.1)',
  },
  circle1: {
    width: 100,
    height: 100,
    top: height * 0.1,
    left: width * 0.1,
  },
  circle2: {
    width: 150,
    height: 150,
    bottom: height * 0.15,
    right: width * 0.05,
  },
  circle3: {
    width: 80,
    height: 80,
    top: height * 0.7,
    left: width * 0.15,
  },
});

export default LoadingScreen;
