import { Role } from './role.entity';
export declare class Permission {
    id: string;
    name: string;
    displayName: string;
    description?: string;
    resource: string;
    action: string;
    isActive: boolean;
    conditions?: Record<string, any>;
    roles: Role[];
    createdAt: Date;
    updatedAt: Date;
}
export declare const PERMISSIONS: {
    readonly SYSTEM_ADMIN: "system.admin";
    readonly SYSTEM_CONFIG: "system.config";
    readonly USERS_READ: "users.read";
    readonly USERS_WRITE: "users.write";
    readonly USERS_DELETE: "users.delete";
    readonly USERS_MANAGE_ROLES: "users.manage_roles";
    readonly SENSORS_READ: "sensors.read";
    readonly SENSORS_WRITE: "sensors.write";
    readonly SENSORS_DELETE: "sensors.delete";
    readonly SENSORS_CALIBRATE: "sensors.calibrate";
    readonly GATES_READ: "gates.read";
    readonly GATES_CONTROL: "gates.control";
    readonly PUMPS_READ: "pumps.read";
    readonly PUMPS_CONTROL: "pumps.control";
    readonly VALVES_READ: "valves.read";
    readonly VALVES_CONTROL: "valves.control";
    readonly GIS_READ: "gis.read";
    readonly GIS_WRITE: "gis.write";
    readonly GIS_ADMIN: "gis.admin";
    readonly REPORTS_READ: "reports.read";
    readonly REPORTS_GENERATE: "reports.generate";
    readonly REPORTS_EXPORT: "reports.export";
    readonly AI_READ: "ai.read";
    readonly AI_EXECUTE: "ai.execute";
    readonly AI_TRAIN: "ai.train";
    readonly IRRIGATION_VIEW_SCHEDULE: "irrigation.view_schedule";
    readonly IRRIGATION_CREATE_SCHEDULE: "irrigation.create_schedule";
    readonly IRRIGATION_MODIFY_SCHEDULE: "irrigation.modify_schedule";
    readonly IRRIGATION_DELETE_SCHEDULE: "irrigation.delete_schedule";
    readonly ALERTS_READ: "alerts.read";
    readonly ALERTS_ACKNOWLEDGE: "alerts.acknowledge";
    readonly ALERTS_CONFIGURE: "alerts.configure";
};
//# sourceMappingURL=permission.entity.d.ts.map