import React from 'react';
import { View, Text, StyleSheet } from 'react-native';

export const PROVIDER_GOOGLE = 'google';

export const Marker = (props: any) => {
    return null;
};

export const Callout = (props: any) => {
    return null;
};

export const Polyline = (props: any) => {
    return null;
};

const MapView = (props: any) => {
    return (
        <View style={[styles.container, props.style]}>
            <Text style={styles.text}>Map not supported on web</Text>
            {props.children}
        </View>
    );
};

const styles = StyleSheet.create({
    container: {
        backgroundColor: '#e1e1e1',
        justifyContent: 'center',
        alignItems: 'center',
    },
    text: {
        color: '#666',
    },
});

export default MapView;
