import Link from "next/link";

export default function NotFound() {
  return (
    <div style={{
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
      minHeight: "60vh",
      fontFamily: "'Public Sans', Arial, sans-serif",
      padding: 24,
    }}>
      <p style={{ fontSize: 64, fontWeight: 700, color: "#CDD3D6", margin: 0 }}>404</p>
      <h2 style={{ color: "#002664", marginTop: 8 }}>Page not found</h2>
      <p style={{ color: "#495054", textAlign: "center", maxWidth: 400 }}>
        The page you are looking for does not exist or the proposal has not been loaded yet.
      </p>
      <Link href="/" style={{
        marginTop: 16,
        background: "#002664",
        color: "white",
        padding: "10px 24px",
        textDecoration: "none",
        fontWeight: 600,
      }}>
        Back to search
      </Link>
    </div>
  );
}
