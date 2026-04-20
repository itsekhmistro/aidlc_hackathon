import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { z } from "zod";
import { api } from "../lib/api";

const schema = z
  .object({
    token: z.string().min(1, "Reset token is required"),
    password: z.string().min(8, "Min 8 characters"),
    confirm: z.string(),
  })
  .refine((d) => d.password === d.confirm, {
    message: "Passwords do not match",
    path: ["confirm"],
  });

type FormData = z.infer<typeof schema>;

export default function ResetPasswordPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const [serverError, setServerError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: { token: params.get("token") ?? "" },
  });

  const onSubmit = async (data: FormData) => {
    setServerError(null);
    try {
      await api.post<void>("/api/auth/password-reset", { token: data.token, new_password: data.password });
      navigate("/login");
    } catch (e) {
      setServerError(e instanceof Error ? e.message : "Reset failed");
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <form
        onSubmit={handleSubmit(onSubmit)}
        className="bg-white p-8 rounded-lg shadow-md w-full max-w-sm space-y-4"
      >
        <h1 className="text-2xl font-bold text-gray-900">Set new password</h1>

        {serverError && (
          <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">
            {serverError}
          </p>
        )}

        <div className="space-y-1">
          <label className="text-sm font-medium text-gray-700">Reset token</label>
          <input
            {...register("token")}
            className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="Paste reset token"
          />
          {errors.token && <p className="text-xs text-red-600">{errors.token.message}</p>}
        </div>

        <div className="space-y-1">
          <label className="text-sm font-medium text-gray-700">New password</label>
          <input
            type="password"
            {...register("password")}
            className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="••••••••"
          />
          {errors.password && <p className="text-xs text-red-600">{errors.password.message}</p>}
        </div>

        <div className="space-y-1">
          <label className="text-sm font-medium text-gray-700">Confirm password</label>
          <input
            type="password"
            {...register("confirm")}
            className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="••••••••"
          />
          {errors.confirm && <p className="text-xs text-red-600">{errors.confirm.message}</p>}
        </div>

        <button
          type="submit"
          disabled={isSubmitting}
          className="w-full bg-blue-600 text-white py-2 rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
        >
          {isSubmitting ? "Saving…" : "Set new password"}
        </button>

        <p className="text-center text-sm text-gray-500">
          <Link to="/login" className="text-blue-600 hover:underline">
            Back to sign in
          </Link>
        </p>
      </form>
    </div>
  );
}
