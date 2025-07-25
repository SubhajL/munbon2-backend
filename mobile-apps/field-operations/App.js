/**
 * Munbon Field Operations Mobile App
 * Offline-first React Native application for field teams
 */

import React, { useEffect } from 'react';
import { StatusBar } from 'react-native';
import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { Provider } from 'react-redux';
import { PersistGate } from 'redux-persist/integration/react';
import NetInfo from '@react-native-community/netinfo';
import SplashScreen from 'react-native-splash-screen';

import { store, persistor } from './src/store';
import { initializeApp } from './src/services/initialization';
import { setupBackgroundSync } from './src/services/backgroundSync';

// Screens
import LoginScreen from './src/screens/LoginScreen';
import DashboardScreen from './src/screens/DashboardScreen';
import ScheduleScreen from './src/screens/ScheduleScreen';
import NavigationScreen from './src/screens/NavigationScreen';
import GateOperationScreen from './src/screens/GateOperationScreen';
import PhotoCaptureScreen from './src/screens/PhotoCaptureScreen';
import SyncScreen from './src/screens/SyncScreen';
import SettingsScreen from './src/screens/SettingsScreen';

// Components
import LoadingScreen from './src/components/LoadingScreen';
import OfflineIndicator from './src/components/OfflineIndicator';

const Stack = createNativeStackNavigator();

const App = () => {
  useEffect(() => {
    // Initialize app
    initializeApp();
    
    // Setup background sync
    setupBackgroundSync();
    
    // Hide splash screen
    SplashScreen.hide();
    
    // Monitor network status
    const unsubscribe = NetInfo.addEventListener(state => {
      console.log('Connection type:', state.type);
      console.log('Is connected?', state.isConnected);
    });
    
    return () => unsubscribe();
  }, []);
  
  return (
    <Provider store={store}>
      <PersistGate loading={<LoadingScreen />} persistor={persistor}>
        <StatusBar barStyle="light-content" backgroundColor="#1e5e3a" />
        <NavigationContainer>
          <Stack.Navigator 
            initialRouteName="Login"
            screenOptions={{
              headerStyle: {
                backgroundColor: '#2e7d32',
              },
              headerTintColor: '#fff',
              headerTitleStyle: {
                fontWeight: 'bold',
              },
            }}
          >
            <Stack.Screen 
              name="Login" 
              component={LoginScreen} 
              options={{ headerShown: false }}
            />
            <Stack.Screen 
              name="Dashboard" 
              component={DashboardScreen}
              options={{ 
                title: 'Field Operations',
                headerLeft: null 
              }}
            />
            <Stack.Screen 
              name="Schedule" 
              component={ScheduleScreen}
              options={{ title: 'Today\'s Schedule' }}
            />
            <Stack.Screen 
              name="Navigation" 
              component={NavigationScreen}
              options={{ title: 'Gate Navigation' }}
            />
            <Stack.Screen 
              name="GateOperation" 
              component={GateOperationScreen}
              options={{ title: 'Gate Operation' }}
            />
            <Stack.Screen 
              name="PhotoCapture" 
              component={PhotoCaptureScreen}
              options={{ title: 'Take Photo' }}
            />
            <Stack.Screen 
              name="Sync" 
              component={SyncScreen}
              options={{ title: 'Data Sync' }}
            />
            <Stack.Screen 
              name="Settings" 
              component={SettingsScreen}
              options={{ title: 'Settings' }}
            />
          </Stack.Navigator>
          <OfflineIndicator />
        </NavigationContainer>
      </PersistGate>
    </Provider>
  );
};

export default App;