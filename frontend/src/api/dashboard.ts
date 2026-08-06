const API_BASE_URL = "http://127.0.0.1:8000";

export async function getDashboardStats() {
    const response = await fetch(`${API_BASE_URL}/dashboard/stats`);

    if (!response.ok) {
        throw new Error("Failed to fetch dashboard stats");
    }

    return response.json();
}