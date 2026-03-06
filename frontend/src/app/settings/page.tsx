"use client";

import { useState, useEffect } from "react";
import { apiFetch } from "@/lib/api";

export default function SettingsPage() {
  const [apiKey, setApiKey] = useState("");
  const [saved, setSaved] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<string | null>(null);

  useEffect(() => {
    setApiKey(localStorage.getItem("rustdali_api_key") || "");
  }, []);

  function handleSave() {
    localStorage.setItem("rustdali_api_key", apiKey.trim());
    setSaved(true);
    setTestResult(null);
    setTimeout(() => setSaved(false), 2000);
  }

  async function handleTest() {
    localStorage.setItem("rustdali_api_key", apiKey.trim());
    setTesting(true);
    setTestResult(null);
    try {
      const res = await apiFetch("/libraries");
      if (res.ok) {
        setTestResult("success");
      } else if (res.status === 401) {
        setTestResult("invalid");
      } else {
        setTestResult("error");
      }
    } catch {
      setTestResult("error");
    } finally {
      setTesting(false);
    }
  }

  return (
    <div className="max-w-lg">
      <h1 className="text-2xl font-bold mb-6">Settings</h1>

      <div className="bg-white rounded-lg border border-gray-200 p-6 space-y-4">
        <div>
          <label className="block text-sm font-medium mb-1">API Key</label>
          <input
            type="password"
            value={apiKey}
            onChange={(e) => {
              setApiKey(e.target.value);
              setSaved(false);
              setTestResult(null);
            }}
            placeholder="Enter your API key"
            className="border rounded px-3 py-2 w-full font-mono text-sm"
          />
          <p className="text-xs text-gray-500 mt-1">
            Stored in your browser only. Get a key from your administrator.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={handleSave}
            className="px-4 py-2 bg-blue-600 text-white rounded text-sm hover:bg-blue-700"
          >
            Save
          </button>
          <button
            onClick={handleTest}
            disabled={testing || !apiKey.trim()}
            className="px-4 py-2 bg-gray-200 text-gray-800 rounded text-sm hover:bg-gray-300 disabled:opacity-50"
          >
            {testing ? "Testing..." : "Test connection"}
          </button>
          {saved && (
            <span className="text-sm text-green-600">Saved</span>
          )}
        </div>

        {testResult === "success" && (
          <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-2 rounded text-sm">
            Connection successful. API key is valid.
          </div>
        )}
        {testResult === "invalid" && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-2 rounded text-sm">
            Invalid API key. Check the key and try again.
          </div>
        )}
        {testResult === "error" && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-2 rounded text-sm">
            Connection failed. Is the backend running?
          </div>
        )}
      </div>
    </div>
  );
}
