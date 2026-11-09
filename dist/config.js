'use strict';
window.BLOOM_API_BASE = (window.Capacitor && window.Capacitor.isNativePlatform && window.Capacitor.isNativePlatform())
  ? 'http://192.168.1.16:4318'
  : '';
