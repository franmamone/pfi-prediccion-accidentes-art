import type { User } from "./api";

export function needsMfaSetup(user: User | null | undefined): boolean {
  if (!user) return false;
  if (user.mfaSetupRequired) return true;
  return !!user.mfaRequired && !user.mfaEnabled;
}
