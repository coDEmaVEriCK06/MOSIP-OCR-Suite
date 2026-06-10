const ENDPOINT = "/api/extract";

export async function extractDocument(file) {
  const form = new FormData();
  form.append("file", file);

  const res = await fetch(ENDPOINT, { method: "POST", body: form });
  const data = await res.json().catch(() => null);

  if (!res.ok) {
    const message =
      data?.message || "Extraction failed. Check the file and try again.";
    const error = new Error(message);
    error.errorType = data?.error_type;
    error.details = data?.details;
    throw error;
  }
  return data;
}
