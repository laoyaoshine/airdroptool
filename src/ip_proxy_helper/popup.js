document.getElementById("addProxy").addEventListener("click", () => {
  const input = document.getElementById("proxyInput").value;
  const [host, port] = input.split(":").map(part => part.trim());
  if (host && port) {
    chrome.runtime.sendMessage({ action: "addProxy", proxy: { host, port: parseInt(port) } }, (response) => {
      if (response.success) updateProxyList();
    });
  }
});

document.getElementById("switchProxy").addEventListener("click", () => {
  const input = document.getElementById("proxyInput").value;
  const [host, port] = input.split(":").map(part => part.trim());
  if (host && port) {
    chrome.runtime.sendMessage({ action: "switchProxy", proxy: { host, port: parseInt(port) } }, (response) => {
      if (response.success) alert("Proxy switched successfully!");
    });
  }
});

function updateProxyList() {
  chrome.runtime.sendMessage({ action: "getProxies" }, (response) => {
    const list = document.getElementById("proxyList");
    list.innerHTML = "";
    response.proxies.forEach(proxy => {
      const li = document.createElement("li");
      li.className = "proxy-item";
      li.textContent = `${proxy.host}:${proxy.port} (Current: ${response.current === proxy ? "Yes" : "No"})`;
      list.appendChild(li);
    });
  });
}

updateProxyList(); // 初始化加载代理列表