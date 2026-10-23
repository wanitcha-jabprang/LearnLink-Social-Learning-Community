(() => {
    const imageInput = document.querySelector("[data-image-input]");
    const imagePreview = document.querySelector("[data-image-preview]");
    const profileImageInput = document.querySelector("[data-profile-image-input]");
    const profileImagePreview = document.querySelector("[data-profile-image-preview]");
    const profileCropper = document.querySelector("[data-profile-cropper]");
    const profileCropperStatus = document.querySelector("[data-profile-cropper-status]");
    const profileCropCanvas = document.querySelector("[data-profile-crop-canvas]");
    const profileImageZoom = document.querySelector("[data-profile-image-zoom]");
    const profileEditForm = document.querySelector("#profile-edit");
    const videoInput = document.querySelector("[data-video-input]");
    const videoPreview = document.querySelector("[data-video-preview]");
    const profileCoverInput = document.querySelector("[data-profile-cover-input]");
    const profileCoverPreview = document.querySelector("[data-profile-cover-preview]");
    const profileCoverSave = document.querySelector("[data-profile-cover-save]");
    const profileCoverStatus = document.querySelector("[data-profile-cover-status]");

    let imageUrl = "";
    let videoUrl = "";
    let profileImageUrl = "";
    let profileCoverUrl = "";
    let profileImage = null;
    let profileImageScale = 1;
    let profileImageCenter = { x: 120, y: 120 };
    let profileImageDragging = false;
    let profileImagePointer = null;

    const clearPreviewUrl = (url) => {
        if (url) URL.revokeObjectURL(url);
    };

    profileCoverInput?.addEventListener("change", () => {
        const file = profileCoverInput.files?.[0];
        if (!file) return;
        if (!file.type.startsWith("image/") || file.size > 10 * 1024 * 1024) {
            profileCoverInput.value = "";
            profileCoverSave.disabled = true;
            profileCoverStatus.textContent = "กรุณาเลือกรูปภาพขนาดไม่เกิน 10 MB";
            return;
        }
        clearPreviewUrl(profileCoverUrl);
        profileCoverUrl = URL.createObjectURL(file);
        profileCoverPreview.src = profileCoverUrl;
        profileCoverPreview.hidden = false;
        profileCoverSave.disabled = false;
        profileCoverStatus.textContent = "ตัวอย่างรูปปกพร้อมแล้ว กดบันทึกรูปปกเพื่อยืนยัน";
    });

    const loadProfileImage = (image, sourceUrl) => {
        profileImage = image;
        profileImageScale = Math.max(
            profileCropCanvas.width / image.naturalWidth,
            profileCropCanvas.height / image.naturalHeight,
        );
        profileImageCenter = {
            x: profileCropCanvas.width / 2,
            y: profileCropCanvas.height / 2,
        };
        profileImageZoom.value = "1";
        profileCropper.hidden = false;
        drawProfileCrop();
        if (profileCropperStatus) {
            profileCropperStatus.textContent = sourceUrl
                ? "รูปพร้อมแล้ว เลื่อนแถบซูมและลากรูปเพื่อจัดตำแหน่ง"
                : "กำลังแสดงรูปโปรไฟล์ปัจจุบัน";
        }
    };

    const drawProfileCrop = () => {
        if (!profileImage || !profileCropCanvas || !profileImageZoom) return;
        const context = profileCropCanvas.getContext("2d");
        if (!context) return;
        const size = profileCropCanvas.width;
        const zoom = Number(profileImageZoom.value);
        const width = profileImage.naturalWidth * profileImageScale * zoom;
        const height = profileImage.naturalHeight * profileImageScale * zoom;
        const minX = size - width / 2;
        const maxX = width / 2;
        const minY = size - height / 2;
        const maxY = height / 2;
        profileImageCenter.x = Math.max(minX, Math.min(maxX, profileImageCenter.x));
        profileImageCenter.y = Math.max(minY, Math.min(maxY, profileImageCenter.y));

        context.clearRect(0, 0, size, size);
        context.drawImage(
            profileImage,
            profileImageCenter.x - width / 2,
            profileImageCenter.y - height / 2,
            width,
            height,
        );
    };

    if (profileImagePreview?.getAttribute("src")) {
        const currentImage = new Image();
        currentImage.onload = () => loadProfileImage(currentImage, "");
        currentImage.onerror = () => {
            if (profileCropperStatus) {
                profileCropperStatus.textContent = "เลือกรูปใหม่เพื่อปรับแต่งรูปโปรไฟล์";
            }
        };
        currentImage.src = profileImagePreview.src;
    }

    profileImageInput?.addEventListener("change", () => {
        const file = profileImageInput.files?.[0];
        if (!file) return;
        if (!["image/jpeg", "image/png", "image/webp"].includes(file.type)
            || file.size > 10 * 1024 * 1024) {
            profileImageInput.value = "";
            if (profileCropperStatus) {
                profileCropperStatus.textContent = "ไฟล์ไม่ถูกต้อง กรุณาเลือก JPG, PNG หรือ WebP ขนาดไม่เกิน 10 MB";
            }
            return;
        }
        clearPreviewUrl(profileImageUrl);
        profileImageUrl = URL.createObjectURL(file);
        const selectedImageUrl = profileImageUrl;
        const selectedImage = new Image();
        selectedImage.onload = () => {
            if (selectedImageUrl !== profileImageUrl) return;
            loadProfileImage(selectedImage, "selected");
        };
        selectedImage.onerror = () => {
            if (selectedImageUrl !== profileImageUrl) return;
            profileImageInput.value = "";
            if (profileCropperStatus) {
                profileCropperStatus.textContent = "เปิดไฟล์นี้ไม่ได้ กรุณาเลือกรูปอื่น";
            }
        };
        selectedImage.src = profileImageUrl;
    });

    profileImageZoom?.addEventListener("input", drawProfileCrop);

    profileCropCanvas?.addEventListener("pointerdown", (event) => {
        if (!profileImage) return;
        profileImageDragging = true;
        profileImagePointer = { x: event.clientX, y: event.clientY };
        profileCropCanvas.setPointerCapture(event.pointerId);
    });

    profileCropCanvas?.addEventListener("pointermove", (event) => {
        if (!profileImageDragging || !profileImagePointer) return;
        const bounds = profileCropCanvas.getBoundingClientRect();
        profileImageCenter.x += (event.clientX - profileImagePointer.x)
            * profileCropCanvas.width / bounds.width;
        profileImageCenter.y += (event.clientY - profileImagePointer.y)
            * profileCropCanvas.height / bounds.height;
        profileImagePointer = { x: event.clientX, y: event.clientY };
        drawProfileCrop();
    });

    profileCropCanvas?.addEventListener("pointerup", () => {
        profileImageDragging = false;
        profileImagePointer = null;
    });
    profileCropCanvas?.addEventListener("pointercancel", () => {
        profileImageDragging = false;
        profileImagePointer = null;
    });

    profileEditForm?.addEventListener("submit", async (event) => {
        if (!profileImage || !profileImageInput || !profileCropCanvas) return;
        event.preventDefault();
        const outputCanvas = document.createElement("canvas");
        outputCanvas.width = 512;
        outputCanvas.height = 512;
        const context = outputCanvas.getContext("2d");
        if (!context) {
            window.alert("ไม่สามารถเตรียมรูปโปรไฟล์ได้ กรุณาลองอีกครั้ง");
            return;
        }
        const scale = outputCanvas.width / profileCropCanvas.width;
        context.drawImage(
            profileImage,
            (profileImageCenter.x - profileCropCanvas.width / 2) * scale,
            (profileImageCenter.y - profileCropCanvas.height / 2) * scale,
            profileImage.naturalWidth * profileImageScale
                * Number(profileImageZoom.value) * scale,
            profileImage.naturalHeight * profileImageScale
                * Number(profileImageZoom.value) * scale,
        );
        outputCanvas.toBlob((blob) => {
            if (!blob) {
                window.alert("ไม่สามารถสร้างรูปโปรไฟล์ได้ กรุณาลองอีกครั้ง");
                return;
            }
            const croppedFile = new File(
                [blob],
                "profile.webp",
                { type: "image/webp" },
            );
            const transfer = new DataTransfer();
            transfer.items.add(croppedFile);
            profileImageInput.files = transfer.files;
            profileEditForm.submit();
        }, "image/webp", 0.92);
    });

    imageInput?.addEventListener("change", () => {
        const file = imageInput.files?.[0];
        if (!file || !imagePreview) return;
        if (!file.type.startsWith("image/") || file.size > 10 * 1024 * 1024) {
            imageInput.value = "";
            imagePreview.hidden = true;
            window.alert("กรุณาเลือกไฟล์รูปภาพขนาดไม่เกิน 10 MB");
            return;
        }
        clearPreviewUrl(imageUrl);
        imageUrl = URL.createObjectURL(file);
        imagePreview.querySelector("img").src = imageUrl;
        imagePreview.hidden = false;
    });

    videoInput?.addEventListener("change", () => {
        const file = videoInput.files?.[0];
        if (!file || !videoPreview) return;
        if (!file.type.startsWith("video/") || file.size > 100 * 1024 * 1024) {
            videoInput.value = "";
            window.alert("กรุณาเลือกไฟล์วิดีโอขนาดไม่เกิน 100 MB");
            return;
        }
        clearPreviewUrl(videoUrl);
        videoUrl = URL.createObjectURL(file);
        videoPreview.src = videoUrl;
        videoPreview.hidden = false;
        videoPreview.onloadedmetadata = () => {
            if (videoPreview.duration <= 180) return;
            videoInput.value = "";
            videoPreview.removeAttribute("src");
            videoPreview.hidden = true;
            clearPreviewUrl(videoUrl);
            videoUrl = "";
            window.alert("วิดีโอต้องมีความยาวไม่เกิน 3 นาที");
        };
    });

    document.querySelector("[data-image-preview] [data-action='remove-image']")?.addEventListener("click", () => {
        clearPreviewUrl(imageUrl);
        imageUrl = "";
        if (imageInput) imageInput.value = "";
        if (imagePreview) imagePreview.hidden = true;
    });
})();
