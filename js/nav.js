(() => {
  const path = location.pathname.replace(/\/+$/, "") || "/";
  const file = path.endsWith(".html")
    ? path.split("/").pop()
    : path === "/" || path.endsWith("/myodani-washoi")
      ? "index.html"
      : `${path.split("/").pop()}.html`;
  document.querySelectorAll(".nav a").forEach((a) => {
    const href = a.getAttribute("href");
    if (href === file || (file === "index.html" && href === "./")) {
      a.setAttribute("aria-current", "page");
    }
  });
})();
