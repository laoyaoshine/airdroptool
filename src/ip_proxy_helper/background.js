// 异步代理管理，实时监控
let proxies = [];
let currentProxy = null;

chrome.storage.local.get(['proxies'], (result) => {
  proxies = result.proxies || [];
});

chrome.runtime.onMessage.addListener(async (message, sender, sendResponse) => {
  if (message.action === "addProxy") {
    proxies.push(message.proxy);
    chrome.storage.local.set({ proxies: proxies }, () => sendResponse({ success: true }));
    return true;
  }
  if (message.action === "switchProxy") {
    currentProxy = message.proxy;
    await chrome.proxy.settings.set({
      value: {
        mode: "fixed_servers",
        rules: {
          proxyForHttp: {
            host: message.proxy.host,
            port: message.proxy.port
          },
          bypassList: ["localhost"]
        }
      },
      scope: "regular"
    });
    sendResponse({ success: true });
    return true;
  }
  if (message.action === "getProxies") {
    sendResponse({ proxies: proxies, current: currentProxy });
    return true;
  }
});

// 实时监控代理状态
chrome.alarms.create("monitorProxies", { periodInMinutes: 1 });
chrome.alarms.onAlarm.addListener(async (alarm) => {
  if (alarm.name === "monitorProxies") {
    for (let proxy of proxies) {
      try {
        const response = await fetch("https://www.google.com", { 
          mode: 'no-cors', 
          proxy: `http://${proxy.host}:${proxy.port}`
        });
        if (!response.ok) {
          console.log(`Proxy ${proxy.host}:${proxy.port} failed, removing...`);
          proxies = proxies.filter(p => p !== proxy);
          chrome.storage.local.set({ proxies: proxies });
        }
      } catch (e) {
        console.log(`Proxy ${proxy.host}:${proxy.port} failed: ${e.message}`);
        proxies = proxies.filter(p => p !== proxy);
        chrome.storage.local.set({ proxies: proxies });
      }
    }
  }
});