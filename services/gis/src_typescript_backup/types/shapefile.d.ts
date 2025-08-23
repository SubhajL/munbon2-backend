declare module 'shapefile' {
  export function open(shpPath: string, dbfPath?: string): Promise<{
    read(): Promise<{
      done: boolean;
      value?: any;
    }>;
  }>;
}