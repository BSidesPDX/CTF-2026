import { Injectable, Logger } from '@nestjs/common';

export type ChallengeEvent =
  | 'contractor.login.failed'
  | 'contractor.login.succeeded'
  | 'contractor.artifact.downloaded'
  | 'archive.login.failed'
  | 'archive.login.succeeded'
  | 'archive.audit.downloaded'
  | 'superadmin.login.failed'
  | 'superadmin.login.succeeded'
  | 'final.artifact.downloaded';

@Injectable()
export class ChallengeTelemetryService {
  private readonly logger = new Logger('ChallengeTelemetry');

  record(event: ChallengeEvent): void {
    this.logger.log(
      JSON.stringify({ event, occurredAt: new Date().toISOString() }),
    );
  }
}
