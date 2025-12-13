import { Client } from "../client.js";
import { v4 as uuidv4 } from "uuid";
// eslint-disable-next-line import/no-extraneous-dependencies
import { faker } from "@faker-js/faker";
import { RunCreate } from "../schemas.js";

export async function toArray<T>(iterable: AsyncIterable<T>): Promise<T[]> {
  const result: T[] = [];
  for await (const item of iterable) {
    result.push(item);
  }
  return result;
}

export async function waitUntil(
  condition: () => Promise<boolean>,
  timeout: number,
  interval: number,
  prefix?: string
): Promise<void> {
  const start = Date.now();
  while (Date.now() - start < timeout) {
    try {
      if (await condition()) {
        return;
      }
    } catch (e) {
      // Pass
    }
    await new Promise((resolve) => setTimeout(resolve, interval));
  }
  const elapsed = Date.now() - start;
  throw new Error(
    [prefix, `Timeout after ${elapsed / 1000}s`].filter(Boolean).join(": ")
  );
}

export async function pollRunsUntilCount(
  client: Client,
  projectName: string,
  count: number,
  timeout?: number
): Promise<void> {
  await waitUntil(
    async () => {
      try {
        const runs = await toArray(client.listRuns({ projectName }));
        return runs.length === count;
      } catch (e) {
        return false;
      }
    },
    timeout ?? 120_000, // Wait up to 120 seconds
    3000
  );
}

export async function deleteProject(
  langchainClient: Client,
  projectName: string
) {
  try {
    await langchainClient.readProject({ projectName });
    await langchainClient.deleteProject({ projectName });
  } catch (e) {
    // Pass
  }
}
export async function deleteDataset(
  langchainClient: Client,
  datasetName: string
) {
  try {
    const existingDataset = await langchainClient.readDataset({ datasetName });
    await langchainClient.deleteDataset({ datasetId: existingDataset.id });
  } catch (e) {
    // Pass
  }
}

export async function waitUntilRunFound(
  client: Client,
  runId: string,
  checkOutputs = false,
  timeout?: number
) {
  return waitUntil(
    async () => {
      try {
        const run = await client.readRun(runId);
        if (checkOutputs) {
          return (
            run.outputs !== null &&
            run.outputs !== undefined &&
            Object.keys(run.outputs).length !== 0
          );
        }
        return true;
      } catch (e) {
        return false;
      }
    },
    timeout ?? 30_000,
    3_000,
    `Waiting for run "${runId}"`
  );
}

export async function waitUntilRunFoundByMetaField(
  client: Client,
  projectName: string,
  metaKey: string,
  metaValue: string,
  checkOutputs = false
) {
  return waitUntil(
    async () => {
      try {
        const runs = await toArray(
          client.listRuns({
            filter: `and(eq(metadata_key, "${metaKey}"), eq(metadata_value, "${metaValue}"))`,
            projectName,
          })
        );
        if (runs.length === 0) {
          return false;
        }
        const run = runs[0];
        if (checkOutputs) {
          return (
            run.outputs !== null &&
            run.outputs !== undefined &&
            Object.keys(run.outputs).length !== 0
          );
        }
        return true;
      } catch (e) {
        return false;
      }
    },
    30_000,
    5_000,
    `Waiting for run with metadata.${metaKey} = "${metaValue}"`
  );
}

export async function waitUntilProjectFound(
  client: Client,
  projectName: string
) {
  return waitUntil(
    async () => {
      try {
        await client.readProject({ projectName });
        return true;
      } catch (e) {
        return false;
      }
    },
    10_000,
    5_000,
    `Waiting for project "${projectName}"`
  );
}

export function sanitizePresignedUrls(payload: unknown) {
  return JSON.parse(JSON.stringify(payload), (key, value) => {
    if (key === "presigned_url") {
      try {
        const url = new URL(value);
        url.searchParams.set("Signature", "[SIGNATURE]");
        url.searchParams.set("Expires", "[EXPIRES]");
        return url.toString();
      } catch {
        return value;
      }
    }
    return value;
  });
}

/**
 * Factory which returns a list of `RunCreate` objects.
 * @param {number} count Number of runs to create (default: 10)
 * @returns {Array<RunCreate>} List of `RunCreate` objects
 */
export function createRunsFactory(
  projectName: string,
  count = 10
): Array<RunCreate> {
  return Array.from({ length: count }).map((_, idx) => ({
    id: uuidv4(),
    name: `${idx}-${faker.lorem.words()}`,
    run_type: faker.helpers.arrayElement(["tool", "chain", "llm", "retriever"]),
    inputs: {
      question: faker.lorem.sentence(),
    },
    outputs: {
      answer: faker.lorem.sentence(),
    },
    project_name: projectName,
  }));
}

/**
 * Helper to check if an error is a rate limit (429) error
 */
export function isRateLimitError(error: any): boolean {
  return (
    error?.status === 429 ||
    error?.statusCode === 429 ||
    error?.message?.includes("429") ||
    error?.message?.includes("Too Many Requests") ||
    error?.message?.includes("Rate limit")
  );
}

/**
 * Wraps a test function to skip gracefully on rate limit errors
 */
export async function skipOnRateLimit(
  testFn: () => Promise<void>
): Promise<void> {
  try {
    await testFn();
  } catch (error: any) {
    if (isRateLimitError(error)) {
      console.log(
        "⚠️  Test skipped due to rate limit (429). This is expected in CI with API rate limits."
      );
      return; // Skip test gracefully
    }
    throw error; // Re-throw other errors
  }
}
export const generateLongContext = () => {
  return `
The current date is ${new Date().toISOString()}.

COMPREHENSIVE ENTERPRISE APPLICATION ERROR ANALYSIS AND SYSTEM DEBUGGING DOCUMENTATION:

================================================================================
PRIMARY ERROR INFORMATION
================================================================================

TypeError: Cannot read properties of undefined (reading 'map')
    at processUserDataCollection (/app/src/utils/dataProcessor.js:45:22)
    at validateUserInputCollection (/app/src/validation/userValidator.js:78:15)
    at handleApiResponseProcessing (/app/src/handlers/apiHandler.js:123:8)
    at processApiDataTransformation (/app/src/services/apiService.js:234:12)
    at async fetchUserDataFromMultipleSources (/app/src/services/userService.js:89:19)
    at async getUserProfileWithPreferences (/app/src/controllers/userController.js:156:23)
    at async authenticateUserAndLoadSession (/app/src/middleware/auth.js:67:18)
    at async initializeApplicationMainProcess (/app/src/index.js:12:5)
    at Object.<anonymous> (/app/src/index.js:25:1)
    at Module._compile (node:internal/modules/cjs/loader:1469:14)
    at Module._extensions..js (node:internal/modules/cjs/loader:1548:10)
    at Module.load (node:internal/modules/cjs/loader:1288:32)
    at Module._load (node:internal/modules/cjs/loader:1104:12)
    at Function.executeUserEntryPoint [as runMain] (node:internal/run_main:154:12)
    at node:internal/main/run_main_module:28:49

================================================================================
DETAILED SYSTEM ARCHITECTURE AND ERROR CONTEXT
================================================================================

This critical error manifests in a complex enterprise-grade Node.js application that processes user data from multiple distributed API endpoints across various microservices. The application architecture encompasses several interconnected systems that communicate through REST APIs, GraphQL endpoints, message queues, and real-time WebSocket connections. The specific error occurs when the dataProcessor utility function attempts to execute the JavaScript .map() method on what the system expects to be an array of user objects, but instead receives an undefined value due to various upstream failures or race conditions.

The application serves over 100,000 daily active users across multiple geographic regions and handles complex data transformations including user profile management, preference synchronization, analytics tracking, financial transactions, content delivery, and real-time notifications. The system architecture follows microservices patterns with event-driven communication, distributed caching, and horizontal scaling capabilities.

================================================================================
COMPREHENSIVE SYSTEM ENVIRONMENT AND INFRASTRUCTURE
================================================================================

Production Environment Configuration:
- Node.js Runtime Version: 18.17.0 (LTS with security patches)
- Express.js Framework Version: 4.18.2 with custom middleware
- Database Primary: PostgreSQL 15.3 with read replicas
- Database Secondary: MongoDB 6.0.8 for document storage
- Cache Layer Primary: Redis 7.0.11 cluster with 6 nodes
- Cache Layer Secondary: Memcached 1.6.17 for session data
- Operating System: Ubuntu 22.04 LTS with hardened kernel
- Container Runtime: Docker 24.0.5 with Kubernetes 1.27.3
- Memory Allocation: 8GB heap size with 2GB for V8 garbage collection
- CPU Resources: 16 virtual cores across 4 physical cores
- Load Balancer: NGINX 1.22.1 with SSL termination and compression
- Reverse Proxy: HAProxy 2.8.1 for advanced load balancing
- Message Queue: Apache Kafka 3.5.0 with 3 broker cluster
- Search Engine: Elasticsearch 8.8.2 with 5-node cluster
- Monitoring: Prometheus 2.45.0 with Grafana 10.0.2 dashboards
- Logging: ELK Stack with Filebeat, Logstash, and centralized logging
- Security: OAuth 2.0, JWT tokens, API rate limiting, DDoS protection

Development and Staging Environments:
- Docker Compose with service replication
- Kubernetes minikube for local development
- Jenkins CI/CD pipeline with automated testing
- SonarQube code quality analysis
- Snyk security vulnerability scanning
- Jest test framework with 85%+ code coverage
- ESLint and Prettier for code formatting
- Husky pre-commit hooks for quality gates

================================================================================
ENTERPRISE APPLICATION ARCHITECTURE OVERVIEW
================================================================================

The application implements a sophisticated microservices architecture with the following core components and their responsibilities:

1. API Gateway Service (Port 3000):
   - Handles all incoming HTTP requests and routing decisions
   - Implements rate limiting with Redis-backed token buckets
   - Manages API versioning and backward compatibility
   - Enforces authentication and authorization policies
   - Provides request/response transformation and validation
   - Implements circuit breakers for downstream service protection
   - Tracks API usage metrics and performance analytics

2. Authentication and Authorization Service (Port 3001):
   - JWT token generation, validation, and refresh mechanisms
   - OAuth 2.0 integration with Google, Facebook, and Microsoft
   - Multi-factor authentication with SMS and email verification
   - Role-based access control (RBAC) with fine-grained permissions
   - Session management with Redis-based storage
   - Password policies and security audit logging
   - Single Sign-On (SSO) integration with SAML and OpenID Connect

3. User Profile Management Service (Port 3002):
   - Comprehensive user profile data management and CRUD operations
   - User preference storage and synchronization across devices
   - Avatar and file upload handling with AWS S3 integration
   - User activity tracking and behavioral analytics
   - Privacy settings management and GDPR compliance features
   - User relationship management (friends, followers, connections)
   - Advanced search and filtering capabilities with Elasticsearch

4. Data Processing and Transformation Service (Port 3003):
   - Real-time data validation and sanitization pipelines
   - Complex data transformation workflows with configurable rules
   - ETL processes for data warehouse synchronization
   - Machine learning model integration for data enrichment
   - Batch processing jobs with queue management
   - Data quality monitoring and anomaly detection
   - Integration with external data sources and APIs

5. Notification and Communication Service (Port 3004):
   - Multi-channel notification delivery (email, SMS, push, in-app)
   - Template management system with dynamic content rendering
   - Delivery tracking and analytics with engagement metrics
   - Preference-based notification filtering and scheduling
   - Integration with SendGrid, Twilio, and Firebase Cloud Messaging
   - Real-time WebSocket notifications for instant messaging
   - Notification history and audit trails for compliance

6. Analytics and Reporting Service (Port 3005):
   - Real-time user behavior tracking and event collection
   - Custom dashboard creation with interactive visualizations
   - A/B testing framework with statistical significance analysis
   - Business intelligence reporting with scheduled delivery
   - Data export capabilities in multiple formats (CSV, JSON, PDF)
   - Performance monitoring and application health metrics
   - Integration with Google Analytics and third-party tracking tools

7. File Storage and Content Delivery Service (Port 3006):
   - Scalable file upload and download management
   - Image processing and optimization with multiple size variants
   - Content Delivery Network (CDN) integration with CloudFront
   - File metadata extraction and search indexing
   - Virus scanning and security validation for uploads
   - Backup and disaster recovery with cross-region replication
   - Digital asset management with version control

8. Distributed Cache and Session Management Layer:
   - Redis cluster for high-performance caching and session storage
   - Cache invalidation strategies with event-driven updates
   - Distributed locking mechanisms for critical sections
   - Session replication across multiple application instances
   - Cache warming strategies for improved performance
   - Memory optimization and garbage collection tuning
   - Cache analytics and performance monitoring

================================================================================
ERROR FREQUENCY ANALYSIS AND OPERATIONAL METRICS
================================================================================

Detailed Error Occurrence Patterns:
- Primary occurrence rate: 15-20 instances per hour during peak traffic periods
- Secondary spikes: 45-60 instances per hour during system maintenance windows
- Geographic distribution: 40% US East, 30% Europe, 20% Asia Pacific, 10% other regions
- Time-based patterns: Higher frequency during business hours (9 AM - 6 PM local time)
- User impact correlation: Affects 2-3% of concurrent user sessions during peak load
- System load correlation: Directly proportional to concurrent user count (>1000 users)
- Database performance correlation: Coincides with connection pool exhaustion events
- Third-party API correlation: Often occurs during external service rate limiting periods
- Recovery characteristics: Automatic recovery typically occurs within 30-60 seconds
- Manual intervention requirements: Required in <5% of cases for complete resolution

Performance Impact Metrics:
- Average response time increase: 2.5x normal during error periods
- CPU utilization spike: 85-95% during error handling
- Memory consumption increase: 40-60% above baseline
- Database connection pool usage: 90-100% utilization
- Cache hit ratio degradation: 15-25% reduction
- Network bandwidth utilization: 30% increase due to retry logic
- Error rate propagation: Cascades to 3-4 downstream services
- User session termination rate: 8-12% of affected sessions

================================================================================
DETAILED CODE ANALYSIS AND ROOT CAUSE INVESTIGATION
================================================================================

The problematic code section located in /app/src/utils/dataProcessor.js (lines 40-55):

function processUserDataCollection(userData, processingOptions = {}) {
  // Critical error location: userData parameter validation missing
  // This function expects an array but sometimes receives undefined
  // due to upstream service failures or race conditions
  
  const {
    enableValidation = true,
    transformationRules = [],
    sanitizationLevel = 'standard',
    auditLogging = false
  } = processingOptions;

  if (auditLogging) {
    logger.info('Processing user data collection', {
      dataLength: userData?.length,
      options: processingOptions,
      timestamp: new Date().toISOString()
    });
  }

  // ERROR OCCURS HERE: userData.map() called on undefined value
  return userData.map(user => ({
    id: user.id,
    name: sanitizeName(user.name, sanitizationLevel),
    email: validateEmail(user.email, enableValidation),
    preferences: processPreferences(user.preferences, transformationRules),
    metadata: enrichMetadata(user.metadata),
    profileImage: processImageUrls(user.profileImage),
    lastLoginTime: formatTimestamp(user.lastLoginTime),
    accountStatus: determineAccountStatus(user),
    permissions: calculateUserPermissions(user.roles),
    analyticsData: generateAnalyticsMetadata(user)
  }));
}

Related upstream code in /app/src/services/userService.js (lines 85-105):

async function fetchUserDataFromMultipleSources(userIds, options = {}) {
  try {
    const promises = [
      fetchFromPrimaryDatabase(userIds),
      fetchFromCacheLayer(userIds),
      fetchFromExternalAPIs(userIds, options)
    ];
    
    const [dbData, cacheData, apiData] = await Promise.allSettled(promises);
    
    // POTENTIAL ISSUE: Merge logic may result in undefined
    const mergedData = mergeUserDataSources(dbData, cacheData, apiData);
    
    // ISSUE: No validation that mergedData is a valid array
    return mergedData;
  } catch (error) {
    logger.error('Failed to fetch user data from multiple sources', error);
    // CRITICAL ISSUE: Returns undefined instead of empty array
    return undefined;
  }
}
    `.trim();
};
