export interface PaginationOptions {
  page: number;
  limit: number;
  sort?: string;
  order?: 'ASC' | 'DESC';
}

export interface PaginatedResponse<T> {
  data: T[];
  total: number;
  page: number;
  limit: number;
  totalPages: number;
}