import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link } from "react-router-dom";
import { z } from "zod";
import { api } from "../lib/api";

const schema = z.object({ email: z.string().email("Invalid email address") });
type FormData = z.infer<typeof schema>;

export default function ForgotPasswordPage() {
  const [resetToken, setResetToken] = useState<string | null>(null);
  const [serverError, setServerError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormData>({ resolver: zodResolver(schema) });

  const onSubmit = async (data: FormData) => {
    setServerError(null);
    try {
      const res = await api.post<{ reset_token?: string; message?: string }>(
        "/api/auth/password-reset-request",
        data,
      );
      setResetToken(res.reset_token ?? null);
    } catch (e) {
      setServerError(e instanceof Error ? e.message : "Request failed");
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="bg-white p-8 rounded-lg shadow-md w-full max-w-sm space-y-4">
        <h1 className="text-2xl font-bold text-gray-900">Reset password</h1>

        {resetToken ? (
          <div className="space-y-3">
            <p className="text-sm text-gray-600">
              Reset token (dev mode — copy and use at{" "}
              <Link to="/reset-password" className="text-blue-600 underline">
                /reset-password
              </Link>
              ):
            </p>
            <code className="block bg-gray-100 rounded p-2 text-xs break-all">{resetToken}</code>
            <Link
              to={`/reset-password?token=${resetToken}`}
              className="block text-center bg-blue-600 text-white py-2 rounded-md text-sm font-medium hover:bg-blue-700"
            >
              Continue to reset
            </Link>
          </div>
        ) : (
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            {serverError && (
              <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">
                {serverError}
              </p>
            )}

            <div className="space-y-1">
              <label className="text-sm font-medium text-gray-700">Email</label>
              <input
                type="email"
                {...register("email")}
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="you@example.com"
                autoFocus
              />
              {errors.email && <p className="text-xs text-red-600">{errors.email.message}</p>}
            </div>

            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full bg-blue-600 text-white py-2 rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              {isSubmitting ? "Sending…" : "Send reset link"}
            </button>

            <p className="text-center text-sm text-gray-500">
              <Link to="/login" className="text-blue-600 hover:underline">
                Back to sign in
              </Link>
            </p>
          </form>
        )}
      </div>
    </div>
  );
}
