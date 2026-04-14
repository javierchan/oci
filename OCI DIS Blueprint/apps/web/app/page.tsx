export default function HomePage(): JSX.Element {
  return (
    <main
      style={{
        minHeight: "100vh",
        display: "grid",
        placeItems: "center",
        margin: 0,
        fontFamily: "sans-serif",
      }}
    >
      <section style={{ textAlign: "center" }}>
        <h1>OCI DIS Blueprint</h1>
        <p>Web container is running.</p>
      </section>
    </main>
  );
}
