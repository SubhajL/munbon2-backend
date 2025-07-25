/**
 * Dashboard Screen - Main hub for field operations
 */

import React, { useEffect, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  RefreshControl,
  Alert,
} from 'react-native';
import { useSelector, useDispatch } from 'react-redux';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';
import { Card, Badge, ProgressBar } from 'react-native-paper';
import { useNavigation } from '@react-navigation/native';

import { fetchTodaySchedule } from '../store/scheduleSlice';
import { checkSyncStatus } from '../store/syncSlice';
import { formatDistance } from '../utils/dateUtils';

const DashboardScreen = () => {
  const navigation = useNavigation();
  const dispatch = useDispatch();
  const [refreshing, setRefreshing] = useState(false);
  
  const { user, team } = useSelector(state => state.auth);
  const { todayOperations, completedCount } = useSelector(state => state.schedule);
  const { lastSyncTime, pendingReports } = useSelector(state => state.sync);
  const { isConnected } = useSelector(state => state.network);
  
  useEffect(() => {
    loadDashboardData();
  }, []);
  
  const loadDashboardData = async () => {
    try {
      await dispatch(fetchTodaySchedule()).unwrap();
      await dispatch(checkSyncStatus()).unwrap();
    } catch (error) {
      console.error('Failed to load dashboard:', error);
    }
  };
  
  const onRefresh = async () => {
    setRefreshing(true);
    await loadDashboardData();
    setRefreshing(false);
  };
  
  const getProgress = () => {
    if (todayOperations.length === 0) return 0;
    return completedCount / todayOperations.length;
  };
  
  const handleStartWork = () => {
    if (todayOperations.length === 0) {
      Alert.alert('No Operations', 'No operations scheduled for today');
      return;
    }
    navigation.navigate('Schedule');
  };
  
  return (
    <ScrollView 
      style={styles.container}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
      }
    >
      {/* Header */}
      <View style={styles.header}>
        <Text style={styles.greeting}>สวัสดี, {user?.name}</Text>
        <Text style={styles.team}>{team?.name}</Text>
        <Text style={styles.date}>{new Date().toLocaleDateString('th-TH', { 
          weekday: 'long', 
          year: 'numeric', 
          month: 'long', 
          day: 'numeric' 
        })}</Text>
      </View>
      
      {/* Progress Card */}
      <Card style={styles.card}>
        <Card.Content>
          <Text style={styles.cardTitle}>Today's Progress</Text>
          <View style={styles.progressContainer}>
            <ProgressBar 
              progress={getProgress()} 
              color="#2e7d32"
              style={styles.progressBar}
            />
            <Text style={styles.progressText}>
              {completedCount} of {todayOperations.length} completed
            </Text>
          </View>
        </Card.Content>
      </Card>
      
      {/* Quick Actions */}
      <View style={styles.actionsContainer}>
        <TouchableOpacity 
          style={[styles.actionButton, styles.primaryAction]}
          onPress={handleStartWork}
        >
          <Icon name="play-circle" size={48} color="#fff" />
          <Text style={styles.actionText}>Start Work</Text>
        </TouchableOpacity>
        
        <TouchableOpacity 
          style={styles.actionButton}
          onPress={() => navigation.navigate('Navigation')}
        >
          <Icon name="map-marker-path" size={48} color="#2e7d32" />
          <Text style={styles.actionText}>Navigate</Text>
        </TouchableOpacity>
      </View>
      
      {/* Status Cards */}
      <View style={styles.statusGrid}>
        <Card style={styles.statusCard}>
          <Card.Content>
            <Icon name="gate" size={32} color="#1976d2" />
            <Text style={styles.statusValue}>{todayOperations.length}</Text>
            <Text style={styles.statusLabel}>Gates Today</Text>
          </Card.Content>
        </Card>
        
        <Card style={styles.statusCard}>
          <Card.Content>
            <Icon name="clock-outline" size={32} color="#f57c00" />
            <Text style={styles.statusValue}>
              {todayOperations.reduce((sum, op) => sum + op.estimated_duration_minutes, 0) / 60} hrs
            </Text>
            <Text style={styles.statusLabel}>Est. Time</Text>
          </Card.Content>
        </Card>
      </View>
      
      {/* Sync Status */}
      <Card style={styles.card}>
        <Card.Content>
          <View style={styles.syncHeader}>
            <Text style={styles.cardTitle}>Sync Status</Text>
            <Badge 
              size={12} 
              style={[
                styles.syncBadge,
                { backgroundColor: isConnected ? '#4caf50' : '#f44336' }
              ]} 
            />
          </View>
          
          <View style={styles.syncInfo}>
            <Text style={styles.syncText}>
              Last sync: {lastSyncTime ? formatDistance(lastSyncTime) : 'Never'}
            </Text>
            {pendingReports > 0 && (
              <Text style={styles.pendingText}>
                {pendingReports} reports pending sync
              </Text>
            )}
          </View>
          
          <TouchableOpacity 
            style={styles.syncButton}
            onPress={() => navigation.navigate('Sync')}
            disabled={!isConnected}
          >
            <Icon name="sync" size={20} color={isConnected ? '#2e7d32' : '#999'} />
            <Text style={[
              styles.syncButtonText,
              { color: isConnected ? '#2e7d32' : '#999' }
            ]}>
              Sync Now
            </Text>
          </TouchableOpacity>
        </Card.Content>
      </Card>
      
      {/* Next Operation Preview */}
      {todayOperations.length > completedCount && (
        <Card style={styles.card}>
          <Card.Content>
            <Text style={styles.cardTitle}>Next Operation</Text>
            <View style={styles.nextOperation}>
              <Icon name="gate" size={24} color="#666" />
              <View style={styles.nextOperationInfo}>
                <Text style={styles.gateName}>
                  {todayOperations[completedCount]?.gate_name}
                </Text>
                <Text style={styles.gateLocation}>
                  {todayOperations[completedCount]?.physical_markers}
                </Text>
              </View>
              <Icon name="chevron-right" size={24} color="#666" />
            </View>
          </Card.Content>
        </Card>
      )}
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
  header: {
    backgroundColor: '#2e7d32',
    padding: 20,
    paddingTop: 30,
  },
  greeting: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#fff',
  },
  team: {
    fontSize: 16,
    color: '#fff',
    marginTop: 4,
  },
  date: {
    fontSize: 14,
    color: '#fff',
    marginTop: 8,
    opacity: 0.8,
  },
  card: {
    margin: 16,
    marginBottom: 8,
    elevation: 2,
  },
  cardTitle: {
    fontSize: 18,
    fontWeight: '600',
    marginBottom: 12,
    color: '#333',
  },
  progressContainer: {
    marginTop: 8,
  },
  progressBar: {
    height: 8,
    borderRadius: 4,
  },
  progressText: {
    marginTop: 8,
    fontSize: 14,
    color: '#666',
    textAlign: 'center',
  },
  actionsContainer: {
    flexDirection: 'row',
    paddingHorizontal: 16,
    marginTop: 8,
    gap: 12,
  },
  actionButton: {
    flex: 1,
    backgroundColor: '#fff',
    borderRadius: 12,
    padding: 20,
    alignItems: 'center',
    elevation: 2,
  },
  primaryAction: {
    backgroundColor: '#2e7d32',
  },
  actionText: {
    marginTop: 8,
    fontSize: 16,
    fontWeight: '600',
    color: '#333',
  },
  statusGrid: {
    flexDirection: 'row',
    paddingHorizontal: 16,
    marginTop: 16,
    gap: 12,
  },
  statusCard: {
    flex: 1,
    elevation: 2,
  },
  statusValue: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#333',
    marginTop: 8,
  },
  statusLabel: {
    fontSize: 12,
    color: '#666',
    marginTop: 4,
  },
  syncHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  syncBadge: {
    width: 12,
    height: 12,
  },
  syncInfo: {
    marginTop: 8,
  },
  syncText: {
    fontSize: 14,
    color: '#666',
  },
  pendingText: {
    fontSize: 14,
    color: '#f57c00',
    marginTop: 4,
  },
  syncButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 12,
    padding: 8,
    borderWidth: 1,
    borderColor: '#e0e0e0',
    borderRadius: 8,
  },
  syncButtonText: {
    marginLeft: 8,
    fontSize: 14,
    fontWeight: '500',
  },
  nextOperation: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 8,
  },
  nextOperationInfo: {
    flex: 1,
    marginLeft: 12,
  },
  gateName: {
    fontSize: 16,
    fontWeight: '500',
    color: '#333',
  },
  gateLocation: {
    fontSize: 14,
    color: '#666',
    marginTop: 2,
  },
});

export default DashboardScreen;