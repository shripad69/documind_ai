import axios from 'axios';

const api = axios.create({
  baseURL: process.env.REACT_APP_API_URL || 'http://localhost:8000',
  withCredentials: true,
  timeout: 360000,
});

export function getErrorMessage(error) {
  const detail = error?.response?.data?.detail;
  if (typeof detail === 'string' && detail.trim()) return detail;
  if (Array.isArray(detail)) {
    const message = detail.map(item => typeof item === 'string' ? item : item?.msg).filter(Boolean).join(' · ');
    if (message) return message;
  }
  return error?.message || 'Something went wrong.';
}

export default api;
