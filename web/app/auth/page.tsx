import AuthForm from "@/components/auth/AuthForm";

export default function AuthPage() {
  return (
    <main className="flex items-center justify-center p-gutter min-h-dvh">
      <AuthForm />

      {/* Subtle Background Elements — Stitch HTML */}
      <div className="fixed top-20 right-20 w-64 h-64 rounded-full bg-primary/5 blur-[80px] -z-10" />
      <div className="fixed bottom-20 left-20 w-80 h-80 rounded-full bg-secondary/5 blur-[100px] -z-10" />
    </main>
  );
}
