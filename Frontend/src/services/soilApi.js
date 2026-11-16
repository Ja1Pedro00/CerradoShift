
const API_URL = (
  import.meta.env.VITE_API_BASE_URL ||
  import.meta.env.VITE_API_URL ||
  "http://127.0.0.1:8000"
).replace(/\/$/, "");

export async function diagnoseSoil(payload) {
  const controller = new AbortController();

  // Limite temporário para consultas externas.
  const timer = setTimeout(() => {
    controller.abort();
  }, 90000);

  try {
    const response = await fetch(
      `${API_URL}/v1/region/soil-diagnose`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
        signal: controller.signal,
      }
    );

    const data = await response.json();

    if (!response.ok) {
      throw new Error(
        typeof data.detail === "string"
          ? data.detail
          : JSON.stringify(
              data.detail || data
            )
      );
    }

    return data;
  } catch (error) {
    if (error.name === "AbortError") {
      throw new Error(
        "A consulta excedeu o tempo limite. " +
        "Verifique a disponibilidade dos provedores."
      );
    }

    throw error;
  } finally {
    clearTimeout(timer);
  }
}
