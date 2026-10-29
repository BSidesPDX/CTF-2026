import { Injectable } from '@nestjs/common';
import manifest from './challenge-manifest.json';

export interface ChallengeStageConfig {
  companyName: string;
  contractorName: string;
  facilityName: string;
  facilityCode: string;
  incidentName: string;
  incidentCode: string;
  projectCode: string;
  fieldPacketCode: string;
  contractorLogin: {
    username: string;
    password: string;
  };
  archiveLogin: {
    username: string;
    password: string;
  };
  superadminRoute: string;
  superadminLogin: {
    username: string;
    password: string;
  };
  tiffZipPassword: string;
  finalPdfPassword: string;
  flags: {
    phone: string;
    tiff: string;
    stego: string;
    superadmin: string;
    final: string;
  };
}

@Injectable()
export class ChallengeService {
  private readonly config = manifest as ChallengeStageConfig;

  getConfig(): ChallengeStageConfig {
    return this.config;
  }

  validateContractorLogin(username: string, password: string): boolean {
    return (
      username === this.config.contractorLogin.username &&
      password === this.config.contractorLogin.password
    );
  }

  validateArchiveLogin(username: string, password: string): boolean {
    return (
      username === this.config.archiveLogin.username &&
      password === this.config.archiveLogin.password
    );
  }

  validateSuperadminLogin(username: string, password: string): boolean {
    return (
      username === this.config.superadminLogin.username &&
      password === this.config.superadminLogin.password
    );
  }
}
