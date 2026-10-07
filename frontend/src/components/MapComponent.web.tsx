import React from 'react';
import { View, Text, StyleSheet } from 'react-native';

export const PROVIDER_GOOGLE = 'google';

// Mirrors the native shim's export so screens can import one name on every
// platform. Irrelevant here: the web MapView below is a placeholder that renders
// no map at all.
export const MAP_PROVIDER = undefined;

export const Marker = (props: any) => {
    return null;
};

export const Callout = (props: any) => {
    return null;
};

export const Polyline = (props: any) => {
    return null;
};

export const Circle = (props: any) => {
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
