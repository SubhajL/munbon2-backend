# Infrastructure Control Flow Diagrams

## 1. Complete Irrigation Control Flow

```mermaid
sequenceDiagram
    participant User
    participant AWD as AWD Control Service
    participant Kafka
    participant SCADA as SCADA Integration
    participant OPC as OPC UA Server
    participant Gate as Physical Gate
    participant Pump as Physical Pump
    participant Sensor as Water Level Sensor

    User->>AWD: Start Irrigation Request
    AWD->>AWD: Check field configuration
    AWD->>AWD: Calculate required flow rate
    
    rect rgb(200, 220, 250)
        Note over AWD: Pre-Irrigation Checks
        AWD->>Sensor: Get current water level
        Sensor-->>AWD: Current level: 2.5cm
        AWD->>AWD: Verify gates operational
        AWD->>AWD: Check pump availability
        AWD->>AWD: Verify canal capacity
    end
    
    AWD->>Kafka: Publish pump start command
    Kafka->>SCADA: Pump start command
    
    rect rgb(250, 220, 200)
        Note over SCADA,Pump: Pump Start Sequence
        SCADA->>OPC: Write pump start signal
        OPC->>Pump: Start motor
        Pump-->>OPC: Motor running
        OPC-->>SCADA: Status: Running
        SCADA->>OPC: Ramp to speed
        OPC->>Pump: Set speed 80%
        Pump-->>OPC: Speed achieved
    end
    
    SCADA->>Kafka: Pump running confirmation
    Kafka->>AWD: Pump started
    
    AWD->>Kafka: Publish gate open command
    Kafka->>SCADA: Gate open command
    
    rect rgb(220, 250, 200)
        Note over SCADA,Gate: Gate Control
        SCADA->>OPC: Write gate position 60%
        OPC->>Gate: Move to 60% open
        Gate-->>OPC: Position: 60%
        OPC-->>SCADA: Gate at target
    end
    
    SCADA->>Kafka: Gate opened
    Kafka->>AWD: Gate at position
    
    loop Every 5 minutes
        AWD->>Sensor: Read water level
        Sensor-->>AWD: Current level
        AWD->>AWD: Calculate flow rate
        AWD->>AWD: Check for anomalies
        
        alt Water level reached target
            AWD->>Kafka: Close gate command
            AWD->>Kafka: Stop pump command
        else Low flow detected
            AWD->>Kafka: Increase gate opening
        else Rapid drop detected
            AWD->>Kafka: Emergency stop
        end
    end
```

## 2. Gate Control State Machine

```mermaid
stateDiagram-v2
    [*] --> Closed: Initial State
    
    Closed --> Opening: Open Command
    Opening --> Open: Position Reached
    Opening --> Fault: Movement Timeout
    Opening --> Closing: Cancel Command
    
    Open --> Closing: Close Command
    Open --> Adjusting: Adjust Command
    
    Adjusting --> Open: New Position Reached
    Adjusting --> Fault: Movement Error
    
    Closing --> Closed: Fully Closed
    Closing --> Fault: Obstruction Detected
    Closing --> Opening: Emergency Open
    
    Fault --> Maintenance: Maintenance Mode
    Maintenance --> Closed: Reset Complete
    
    state Opening {
        [*] --> StartMotor
        StartMotor --> Accelerating
        Accelerating --> Moving
        Moving --> Decelerating
        Decelerating --> [*]
    }
    
    state Fault {
        [*] --> AnalyzingFault
        AnalyzingFault --> MotorOverload
        AnalyzingFault --> PositionError
        AnalyzingFault --> CommunicationLoss
    }
```

## 3. Water Distribution Network

```mermaid
graph TB
    subgraph "Water Source"
        R[Reservoir]
        C[Main Canal]
    end
    
    subgraph "Primary Distribution"
        MG1[Main Gate 1<br/>Capacity: 50 m³/s]
        MG2[Main Gate 2<br/>Capacity: 50 m³/s]
        P1[Pump Station 1<br/>3 x 500kW pumps]
        P2[Pump Station 2<br/>2 x 750kW pumps]
    end
    
    subgraph "Secondary Distribution"
        SC1[Secondary Canal 1]
        SC2[Secondary Canal 2]
        SC3[Secondary Canal 3]
        DG1[Distribution Gate 1.1]
        DG2[Distribution Gate 1.2]
        DG3[Distribution Gate 2.1]
        DG4[Distribution Gate 3.1]
    end
    
    subgraph "Field Level"
        F1[Field A<br/>10 hectares]
        F2[Field B<br/>15 hectares]
        F3[Field C<br/>8 hectares]
        F4[Field D<br/>12 hectares]
        FG1[Field Gate A]
        FG2[Field Gate B]
        FG3[Field Gate C]
        FG4[Field Gate D]
    end
    
    R --> C
    C --> MG1
    C --> MG2
    MG1 --> P1
    MG2 --> P2
    P1 --> SC1
    P1 --> SC2
    P2 --> SC3
    
    SC1 --> DG1 --> FG1 --> F1
    SC1 --> DG2 --> FG2 --> F2
    SC2 --> DG3 --> FG3 --> F3
    SC3 --> DG4 --> FG4 --> F4
    
    style R fill:#4A90E2
    style P1 fill:#F5A623
    style P2 fill:#F5A623
    style F1 fill:#7ED321
    style F2 fill:#7ED321
    style F3 fill:#7ED321
    style F4 fill:#7ED321
```

## 4. Pump Control Logic

```mermaid
flowchart TD
    Start([Irrigation Request]) --> CheckPower{Power Available?}
    
    CheckPower -->|No| StartGen[Start Generator]
    CheckPower -->|Yes| SelectPump
    StartGen --> SelectPump
    
    SelectPump[Select Optimal Pump] --> PreChecks{Pre-Start Checks}
    
    PreChecks -->|Fail| Alarm[Raise Alarm]
    PreChecks -->|Pass| CloseValve[Close Discharge Valve]
    
    CloseValve --> StartMotor[Start Motor]
    StartMotor --> CheckStart{Motor Started?}
    
    CheckStart -->|No| Retry{Retry < 3?}
    Retry -->|Yes| StartMotor
    Retry -->|No| Fault[Fault Condition]
    
    CheckStart -->|Yes| RampSpeed[Ramp to Speed]
    RampSpeed --> CheckSpeed{At Target Speed?}
    
    CheckSpeed -->|No| AdjustVFD[Adjust VFD]
    AdjustVFD --> CheckSpeed
    CheckSpeed -->|Yes| OpenValve[Open Discharge Valve]
    
    OpenValve --> MonitorFlow{Flow Stable?}
    MonitorFlow -->|No| AdjustValve[Adjust Valve]
    AdjustValve --> MonitorFlow
    MonitorFlow -->|Yes| Normal[Normal Operation]
    
    Normal --> Monitor{Monitor Parameters}
    Monitor -->|Anomaly| Protect{Protection Check}
    Monitor -->|Normal| Monitor
    
    Protect -->|Critical| EmergencyStop[Emergency Stop]
    Protect -->|Warning| Adjust[Adjust Operation]
    Adjust --> Monitor
    
    style Start fill:#90EE90
    style Normal fill:#90EE90
    style Fault fill:#FFB6C1
    style EmergencyStop fill:#FF6347
    style Alarm fill:#FFA500
```

## 5. Emergency Response System

```mermaid
flowchart LR
    subgraph Detection
        S1[Flow Sensor]
        S2[Pressure Sensor]
        S3[Level Sensor]
        S4[Vibration Sensor]
        S5[Power Monitor]
    end
    
    subgraph "Anomaly Detection"
        AD[Anomaly Detector]
        ML[ML Model]
        RT[Real-time Analysis]
    end
    
    subgraph "Decision Engine"
        DE[Decision Logic]
        PR[Priority Rules]
        ES[Emergency Sequences]
    end
    
    subgraph "Actions"
        A1[Stop Pumps]
        A2[Close Gates]
        A3[Open Drainage]
        A4[Alert Operators]
        A5[Isolate Section]
    end
    
    S1 --> AD
    S2 --> AD
    S3 --> AD
    S4 --> AD
    S5 --> AD
    
    AD --> ML
    AD --> RT
    ML --> DE
    RT --> DE
    
    DE --> PR
    PR --> ES
    
    ES -->|Flood Risk| A3
    ES -->|Equipment Failure| A1
    ES -->|Leak Detected| A2
    ES -->|All Events| A4
    ES -->|Major Fault| A5
    
    style S1 fill:#E6F3FF
    style S2 fill:#E6F3FF
    style S3 fill:#E6F3FF
    style S4 fill:#E6F3FF
    style S5 fill:#E6F3FF
    style A1 fill:#FFE6E6
    style A2 fill:#FFE6E6
    style A3 fill:#FFE6E6
    style A4 fill:#FFFACD
    style A5 fill:#FFE6E6
```

## 6. Communication Architecture

```mermaid
graph TB
    subgraph "AWD Control Service"
        API[REST API]
        CL[Control Logic]
        ML[ML Engine]
        DB[(PostgreSQL)]
    end
    
    subgraph "Message Bus"
        K1[Kafka Topic:<br/>gate.commands]
        K2[Kafka Topic:<br/>pump.commands]
        K3[Kafka Topic:<br/>sensor.data]
        K4[Kafka Topic:<br/>system.alerts]
    end
    
    subgraph "SCADA Integration Layer"
        SI[SCADA Interface]
        OPC[OPC UA Client]
        MB[Modbus Client]
        Q[Command Queue]
    end
    
    subgraph "Field Infrastructure"
        GE[GE iFix Server]
        PLC1[PLC Station 1]
        PLC2[PLC Station 2]
        RTU[Remote Terminal Units]
    end
    
    subgraph "Physical Devices"
        G1[Gate 1]
        G2[Gate 2]
        P1[Pump 1]
        P2[Pump 2]
        WL[Water Level Sensors]
        FM[Flow Meters]
    end
    
    API --> CL
    CL --> K1
    CL --> K2
    CL <--> DB
    ML <--> DB
    
    K1 --> SI
    K2 --> SI
    K3 <-- SI
    K4 <-- SI
    
    SI --> Q
    Q --> OPC
    Q --> MB
    
    OPC <--> GE
    MB <--> RTU
    
    GE --> PLC1
    GE --> PLC2
    PLC1 --> G1
    PLC1 --> P1
    PLC2 --> G2
    PLC2 --> P2
    RTU --> WL
    RTU --> FM
    
    style API fill:#4A90E2
    style K1 fill:#F5A623
    style K2 fill:#F5A623
    style K3 fill:#F5A623
    style K4 fill:#F5A623
    style GE fill:#50E3C2
    style G1 fill:#7ED321
    style G2 fill:#7ED321
    style P1 fill:#7ED321
    style P2 fill:#7ED321
```

## 7. Control Priority Matrix

| Scenario | Gate Priority | Pump Priority | Response Time | Override Level |
|----------|--------------|---------------|---------------|----------------|
| Normal Irrigation | Medium | Medium | 5 minutes | Field Operator |
| Low Water Alert | High | Low | 2 minutes | System Auto |
| Flood Risk | Emergency | Emergency | 30 seconds | System Auto |
| Equipment Failure | High | High | 1 minute | Control Room |
| Power Outage | N/A | Emergency | Immediate | System Auto |
| Maintenance Mode | Low | Low | Manual | Maintenance Team |
| Emergency Stop | Emergency | Emergency | Immediate | Any Operator |

## 8. Data Flow for Decision Making

```mermaid
flowchart TD
    subgraph "Input Data"
        WL[Water Levels]
        FL[Flow Rates]
        PS[Pump Status]
        GS[Gate Status]
        WD[Weather Data]
        SD[Schedule Data]
    end
    
    subgraph "Processing"
        DP[Data Processor]
        AE[Anomaly Engine]
        PE[Prediction Engine]
        OE[Optimization Engine]
    end
    
    subgraph "Decision Making"
        DM[Decision Manager]
        PC[Priority Calculator]
        SC[Safety Checks]
    end
    
    subgraph "Execution"
        CE[Command Executor]
        MQ[Message Queue]
        FB[Feedback Loop]
    end
    
    WL --> DP
    FL --> DP
    PS --> DP
    GS --> DP
    WD --> PE
    SD --> OE
    
    DP --> AE
    DP --> PE
    DP --> OE
    
    AE --> DM
    PE --> DM
    OE --> DM
    
    DM --> PC
    PC --> SC
    SC --> CE
    
    CE --> MQ
    MQ --> FB
    FB --> DP
    
    style WL fill:#E6F3FF
    style FL fill:#E6F3FF
    style PS fill:#E6F3FF
    style GS fill:#E6F3FF
    style DM fill:#FFE6CC
    style CE fill:#E6FFE6
```

These diagrams illustrate the complete flow of how the AWD Control Service manages physical infrastructure, from high-level decision making down to actual hardware control, including safety systems and emergency responses.