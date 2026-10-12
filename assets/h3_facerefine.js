// MiniMax H3 Face Refine action button in SwarmUI history & media viewers
(function() {
    try {
        if (typeof deleteCookie === 'function') {
            deleteCookie('lastparam_input_h3facerefinevideofile');
        }
        let el = document.getElementById('input_h3facerefinevideofile');
        if (el) el.value = '';
    } catch (e) {
        console.error('Error cleaning H3 Face Refine param state:', e);
    }

    if (typeof registerMediaButton !== 'function') {
        console.warn('H3 Face Refine: registerMediaButton is not available');
        return;
    }

    let videoExtensions = ['mp4', 'webm', 'gif', 'mov', 'avi', 'mkv'];

    function isVideoSrc(src) {
        let isDataImage = src.startsWith('data:');
        let isDataVideo = isDataImage && src.toLowerCase().startsWith('data:video/');
        if (isDataVideo) {
            return false;
        }
        if (typeof getMediaType === 'function' && getMediaType(src) === 'video') {
            return true;
        }
        let extension = src.split('.').pop().toLowerCase().split('?')[0];
        return videoExtensions.includes(extension);
    }

    registerMediaButton(
        'H3 Face Refine',
        (src) => {
            if (typeof currentBackendFeatureSet === 'undefined' || !currentBackendFeatureSet.includes('h3_face_refine')) {
                let message = 'H3 Face Refine is not available on the current backend. Please verify ComfyUI-H3-FaceRefine is installed.';
                console.warn('H3 Face Refine: ' + message);
                if (typeof showToast === 'function') {
                    showToast(message);
                }
                return;
            }

            if (!isVideoSrc(src)) {
                if (typeof showToast === 'function') {
                    showToast('H3 Face Refine only operates on video files.');
                }
                return;
            }

            let input_overrides = { 'images': 1 };
            let fullsrc = typeof getImageFullSrc === 'function' ? getImageFullSrc(src) : src;
            let prefix = typeof getImageOutPrefix === 'function' ? getImageOutPrefix() : 'Output';
            // SwarmUI derives clean input IDs by stripping every non-alphanumeric char from the
            // param name lowercased: 'H3 Face Refine Video File' -> h3facerefinevideofile.
            // The legacy 'hfacerefinvideofile' key never matched any registered param and is removed.
            input_overrides['h3facerefinevideofile'] = prefix + '/' + fullsrc;

            // Param names must match the C# registrations exactly (clean-ID derivation):
            // 'H3 Face Target' -> h3facetarget, 'H3 Face Denoise Small Face' -> h3facedenoisesmallface, etc.
            let h3Params = [
                'h3facetarget',
                'h3facedenoise',
                'h3facedenoisesmallface',
                'h3facedenoiselargeface',
                'h3facesteps',
                'h3facecanvassize',
                'h3facefeather',
                'h3facedetectionconfidence',
                'h3facerefimagesize',
                'h3faceprompt',
                'h3facereferenceimage',
                'h3facereferenceimagetwo'
            ];

            // Always read the Face Refine parameters from the Generate panel, matching SwarmUI's clean IDs
            for (let param of h3Params) {
                let elem = document.getElementById('input_' + param);
                if (elem) {
                    let val = typeof getInputVal === 'function' ? getInputVal(elem, false) : (elem.dataset && elem.dataset.filedata ? elem.dataset.filedata : elem.value);
                    if (val != null && val !== '') {
                        input_overrides[param] = val;
                    }
                }
            }

            // Defaults: 1 face pass (Primary), 0.27 denoise (matches the C# parameter default), 6 steps, 22px feather
            if (!input_overrides['h3facetarget']) {
                input_overrides['h3facetarget'] = 'Primary Face (Largest)';
            }
            if (!input_overrides['h3facedenoise']) {
                input_overrides['h3facedenoise'] = 0.27;
            }
            if (!input_overrides['h3facesteps']) {
                input_overrides['h3facesteps'] = 6;
            }
            if (!input_overrides['h3facefeather']) {
                input_overrides['h3facefeather'] = 22;
            }

            // Disarm standard refiners / init images from the session so they cannot contaminate on-demand video refinement
            input_overrides['refinermethod'] = null;
            input_overrides['refinermodel'] = null;
            input_overrides['refinerupscale'] = null;
            input_overrides['initimage'] = null;

            if (typeof showToast === 'function') {
                showToast('Starting H3 Face Refine on video...');
            }

            if (typeof mainGenHandler !== 'undefined' && mainGenHandler.doGenerate) {
                mainGenHandler.doGenerate(input_overrides, {});
            }
        },
        'Refine and restore faces in this video using MiniMax H3 Face Refiner (supports 1 or 2 faces)',
        ['video'],
        true,
        true
    );
})();
