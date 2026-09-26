export interface UnderwritingInput {
  assetValue: number;
  deposit: number;
  financeAmount: number;
  interestRate: number;
  termMonths: number;
  noi: number;
  assetType: 'EV_FLEET' | 'COMMERCIAL_PROPERTY' | 'EQUIPMENT';
  tenantCreditScore?: number;
  batteryHealth?: number;
  vehicleAge?: number;
}

export interface UnderwritingResult {
  monthlyPayment: number;
  annualPayment: number;
  coverageRatio: number;
  riskScore: number;
  decision: 'APPROVED' | 'REFER' | 'REJECTED';
  reasons: string[];
}

export function calculateMonthlyPayment(
  principal: number,
  annualRate: number,
  termMonths: number
): number {
  const monthlyRate = annualRate / 100 / 12;
  if (monthlyRate === 0) return principal / termMonths;
  return (principal * monthlyRate) / (1 - Math.pow(1 + monthlyRate, -termMonths));
}

export function underwrite(input: UnderwritingInput): UnderwritingResult {
  const monthlyPayment = calculateMonthlyPayment(
    input.financeAmount,
    input.interestRate,
    input.termMonths
  );
  const annualPayment = monthlyPayment * 12;
  const coverageRatio = input.noi / annualPayment || 0;

  const reasons: string[] = [];
  let riskPoints = 0;

  if (coverageRatio < 1.0) {
    riskPoints += 40;
    reasons.push('Coverage ratio below 1.0x');
  } else if (coverageRatio < 1.15) {
    riskPoints += 25;
    reasons.push('Coverage ratio below 1.15x');
  } else if (coverageRatio < 1.25) {
    riskPoints += 10;
    reasons.push('Coverage ratio below target 1.25x');
  }

  const depositPct = input.assetValue > 0 ? input.deposit / input.assetValue : 0;
  if (depositPct < 0.1) {
    riskPoints += 20;
    reasons.push('Deposit below 10%');
  } else if (depositPct < 0.2) {
    riskPoints += 10;
    reasons.push('Deposit below 20%');
  }

  if (input.tenantCreditScore !== undefined) {
    if (input.tenantCreditScore < 600) {
      riskPoints += 25;
      reasons.push('Low credit score');
    } else if (input.tenantCreditScore < 650) {
      riskPoints += 15;
      reasons.push('Below-average credit');
    } else if (input.tenantCreditScore < 700) {
      riskPoints += 5;
    }
  }

  if (input.assetType === 'EV_FLEET' && input.batteryHealth !== undefined) {
    if (input.batteryHealth < 85) {
      riskPoints += 20;
      reasons.push('Battery health below 85%');
    } else if (input.batteryHealth < 90) {
      riskPoints += 10;
      reasons.push('Battery health below 90%');
    }
  }

  if (input.vehicleAge !== undefined && input.vehicleAge > 5) {
    riskPoints += 15;
    reasons.push('Asset age above 5 years');
  }

  const riskScore = Math.min(100, riskPoints);

  let decision: UnderwritingResult['decision'];
  if (coverageRatio >= 1.25 && riskScore < 40) {
    decision = 'APPROVED';
  } else if (coverageRatio >= 1.15 && riskScore < 60) {
    decision = 'REFER';
  } else {
    decision = 'REJECTED';
  }

  return {
    monthlyPayment: Math.round(monthlyPayment * 100) / 100,
    annualPayment: Math.round(annualPayment * 100) / 100,
    coverageRatio: Math.round(coverageRatio * 100) / 100,
    riskScore,
    decision,
    reasons,
  };
}
