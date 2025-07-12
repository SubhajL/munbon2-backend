# {{SERVICE_NAME}}

{{SERVICE_DESCRIPTION}}

## Prerequisites

- Node.js 20+
- npm or yarn
- Docker (for containerization)

## Getting Started

### Development

1. Clone this repository
2. Install dependencies:
   ```bash
   npm install
   ```

3. Copy environment variables:
   ```bash
   cp .env.example .env
   ```

4. Run in development mode:
   ```bash
   npm run dev
   ```

### Production

1. Build the application:
   ```bash
   npm run build
   ```

2. Start the application:
   ```bash
   npm start
   ```

### Docker

Build and run with Docker:
```bash
docker build -t {{SERVICE_NAME}} .
docker run -p 3000:3000 {{SERVICE_NAME}}
```

## API Documentation

When the service is running, visit `/api-docs` for Swagger documentation.

## Available Scripts

- `npm run dev` - Run in development mode with hot reload
- `npm run build` - Build TypeScript to JavaScript
- `npm start` - Run the built application
- `npm test` - Run tests
- `npm run test:watch` - Run tests in watch mode
- `npm run test:coverage` - Run tests with coverage
- `npm run lint` - Run ESLint
- `npm run lint:fix` - Fix ESLint errors
- `npm run format` - Format code with Prettier
- `npm run type-check` - Check TypeScript types

## Health Checks

- `/health` - Basic health check
- `/health/ready` - Readiness check (includes dependency checks)

## Project Structure

```
src/
├── config/         # Configuration files
├── controllers/    # Request handlers
├── interfaces/     # TypeScript interfaces
├── middleware/     # Express middleware
├── routes/         # API routes
├── services/       # Business logic
├── utils/          # Utility functions
├── app.ts          # Express app setup
└── index.ts        # Application entry point
```

## Environment Variables

See `.env.example` for all available environment variables.

## Testing

This project uses Jest for testing. Tests are located alongside source files with `.test.ts` or `.spec.ts` extensions.

Run tests:
```bash
npm test
```

## Deployment

### Kubernetes

Apply the Kubernetes manifests:
```bash
kubectl apply -f k8s/
```

## Contributing

1. Create a feature branch
2. Make your changes
3. Write/update tests
4. Ensure all tests pass
5. Submit a pull request