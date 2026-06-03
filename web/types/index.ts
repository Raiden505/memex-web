export type Role = "user" | "assistant";

export interface ForgetCandidate {
  id: string;
  content: string;
  created_at: string;
}

export interface Message {
  id: string;
  role: Role;
  content: string;
  date: Date;
  isError?: boolean;
  pending?: boolean;
  forgetCandidates?: ForgetCandidate[];
}
