import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { colors } from '../../theme';

const MapScreen = () => {
    return (
        <View style={styles.container}>
            <Text style={styles.text}>Map is not supported on web yet.</Text>
        </View>
    );
};

const styles = StyleSheet.create({
    container: {
        flex: 1,
        justifyContent: 'center',
        alignItems: 'center',
        backgroundColor: colors.background,
    },
    text: {
        color: colors.text,
        fontSize: 16,
    },
});

export default MapScreen;
