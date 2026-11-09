/**
 * Attendix AdSense Integration
 * ============================
 * Publisher: ca-pub-9718572719666215
 *
 * Loads the Google AdSense Auto Ads script once per page. Auto Ads
 * automatically finds the best placements across the site.
 *
 * Ad component usage for manual placements (HTML):
 *   <div class="ad-container ad-banner"    data-ad-slot="XXXXXXXXXX"></div>
 *   <div class="ad-container ad-inarticle" data-ad-slot="XXXXXXXXXX"></div>
 *   <div class="ad-container ad-footer"    data-ad-slot="XXXXXXXXXX"></div>
 *
 * Publisher ID resolution order:
 *   1. PUBLISHER_ID constant below (confirmed real ID).
 *   2. <meta name="adsense-client" content="ca-pub-..."> override in HTML.
 *   3. /api/config server endpoint (reads ADSENSE_CLIENT_ID env var).
 *
 * The script is injected exactly once — duplicate injection is prevented.
 * When the publisher ID is unavailable, ad containers remain hidden safely.
 */

(function () {
    'use strict';

    // ----------------------------------------------------------------
    // Confirmed AdSense Publisher ID
    // ----------------------------------------------------------------
    var PUBLISHER_ID = 'ca-pub-9718572719666215';

    // ----------------------------------------------------------------
    // 1. Resolve publisher ID (constant → meta tag → API fallback)
    // ----------------------------------------------------------------
    function resolvePublisherId() {
        // Priority 1: hardcoded confirmed publisher ID
        if (PUBLISHER_ID && PUBLISHER_ID.indexOf('ca-pub-') === 0) {
            return Promise.resolve(PUBLISHER_ID);
        }

        // Priority 2: meta tag override in page <head>
        var meta = document.querySelector('meta[name="adsense-client"]');
        if (meta && meta.content && meta.content.indexOf('ca-pub-') === 0) {
            return Promise.resolve(meta.content.trim());
        }

        // Priority 3: server /api/config (reads ADSENSE_CLIENT_ID env var)
        return fetch('/api/config', { cache: 'no-store' })
            .then(function (r) { return r.ok ? r.json() : {}; })
            .then(function (cfg) {
                if (cfg && cfg.adsense_client && cfg.adsense_client.indexOf('ca-pub-') === 0) {
                    return cfg.adsense_client;
                }
                return null;
            })
            .catch(function () { return null; });
    }

    // ----------------------------------------------------------------
    // 2. The AdSense script is loaded via a static <script> tag in
    //    every page's <head> — no dynamic injection needed.
    //    This function is kept as a no-op to prevent any accidental
    //    duplicate script injection.
    // ----------------------------------------------------------------
    var _scriptLoaded = true; // Always true — static tag handles loading

    function loadAdSenseScript(publisherId) {
        // Static <script> tag in <head> already handles this.
        // No-op: prevents duplicate injection.
    }

    // ----------------------------------------------------------------
    // 3. Render <ins class="adsbygoogle"> for manual ad placements
    //    (Auto Ads will fill the rest automatically)
    // ----------------------------------------------------------------
    function renderAdContainers(publisherId) {
        var containers = document.querySelectorAll('.ad-container[data-ad-slot]');
        containers.forEach(function (container) {
            var slot = container.getAttribute('data-ad-slot');
            if (!slot) return; // No slot assigned — keep hidden until slot is set

            var format = container.classList.contains('ad-inarticle') ? 'fluid' : 'auto';

            var ins = document.createElement('ins');
            ins.className = 'adsbygoogle';
            ins.style.display = 'block';
            ins.setAttribute('data-ad-client', publisherId);
            ins.setAttribute('data-ad-slot', slot);
            ins.setAttribute('data-ad-format', format);
            ins.setAttribute('data-full-width-responsive', 'true');

            container.innerHTML = '';
            container.appendChild(ins);
            container.style.display = 'block';

            try {
                (window.adsbygoogle = window.adsbygoogle || []).push({});
            } catch (e) {
                console.debug('[Attendix Ads] adsbygoogle push error:', e);
            }
        });
    }

    // ----------------------------------------------------------------
    // 4. Hide all containers (safe state when ads cannot load)
    // ----------------------------------------------------------------
    function hideAllContainers() {
        document.querySelectorAll('.ad-container').forEach(function (el) {
            el.style.display = 'none';
        });
    }

    // ----------------------------------------------------------------
    // 5. Main init
    // ----------------------------------------------------------------
    function initAds() {
        resolvePublisherId().then(function (publisherId) {
            if (!publisherId) {
                hideAllContainers();
                return;
            }
            loadAdSenseScript(publisherId);
            renderAdContainers(publisherId);
        });
    }

    // ----------------------------------------------------------------
    // 6. Auto-init on DOM ready; expose for manual re-init if needed
    // ----------------------------------------------------------------
    window.AttendixAds = { init: initAds };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initAds);
    } else {
        initAds();
    }
})();
