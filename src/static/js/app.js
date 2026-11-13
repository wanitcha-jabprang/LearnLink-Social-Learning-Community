class ObjectUrlStore {
    constructor() {
        this.value = "";
    }

    create(file) {
        this.clear();
        this.value = URL.createObjectURL(file);
        return this.value;
    }

    clear() {
        if (this.value) {
            URL.revokeObjectURL(this.value);
            this.value = "";
        }
    }
}

class SiteMessageController {
    constructor() {
        const messages = document.querySelector(".site-messages");
        if (messages) {
            window.setTimeout(() => messages.remove(), 3000);
        }
    }
}

class InlineActionController {
    constructor() {
        document.addEventListener("click", (event) => this.handleClick(event));
    }

    handleClick(event) {
        const action = event.target.closest(
            "[data-confirm], [data-toggle-hidden], [data-hide-element], [data-alert]",
        );
        if (!action) return;

        if (action.dataset.confirm && !window.confirm(action.dataset.confirm)) {
            event.preventDefault();
            return;
        }

        const toggleTarget = document.getElementById(
            action.dataset.toggleHidden,
        );
        toggleTarget?.toggleAttribute("hidden");

        const hideTarget = document.getElementById(action.dataset.hideElement);
        hideTarget?.setAttribute("hidden", "true");

        if (action.dataset.alert) {
            window.alert(action.dataset.alert);
        }
    }
}

class ProfileCoverController {
    constructor() {
        this.input = document.querySelector("[data-profile-cover-input]");
        this.preview = document.querySelector("[data-profile-cover-preview]");
        this.saveButton = document.querySelector("[data-profile-cover-save]");
        this.status = document.querySelector("[data-profile-cover-status]");
        this.previewUrl = new ObjectUrlStore();

        this.input?.addEventListener("change", () => this.updatePreview());
    }

    updatePreview() {
        const file = this.input.files?.[0];
        if (!file) return;
        if (!file.type.startsWith("image/") || file.size > 10 * 1024 * 1024) {
            this.input.value = "";
            this.saveButton.hidden = true;
            this.status.textContent = "กรุณาเลือกรูปภาพขนาดไม่เกิน 10 MB";
            return;
        }

        this.preview.src = this.previewUrl.create(file);
        this.preview.hidden = false;
        this.saveButton.hidden = false;
        this.status.textContent = "ตัวอย่างรูปปกพร้อมแล้ว ตรวจดูแล้วกดบันทึกได้เลย";
    }
}

class ProfileImageCropController {
    constructor() {
        this.input = document.querySelector("[data-profile-image-input]");
        this.preview = document.querySelector("[data-profile-image-preview]");
        this.cropper = document.querySelector("[data-profile-cropper]");
        this.status = document.querySelector("[data-profile-cropper-status]");
        this.canvas = document.querySelector("[data-profile-crop-canvas]");
        this.zoomInput = document.querySelector("[data-profile-image-zoom]");
        this.form = document.querySelector("#profile-edit");
        this.previewUrl = new ObjectUrlStore();

        this.image = null;
        this.imageScale = 1;
        this.imageCenter = { x: 120, y: 120 };
        this.dragging = false;
        this.pointer = null;

        this.bindEvents();
        this.loadExistingImage();
    }

    bindEvents() {
        this.input?.addEventListener("change", () => this.selectImage());
        this.zoomInput?.addEventListener("input", () => this.draw());
        this.canvas?.addEventListener("pointerdown", (event) => {
            if (!this.image) return;
            this.dragging = true;
            this.pointer = { x: event.clientX, y: event.clientY };
            this.canvas.setPointerCapture(event.pointerId);
        });
        this.canvas?.addEventListener("pointermove", (event) => {
            this.moveImage(event);
        });
        this.canvas?.addEventListener("pointerup", () => this.stopDragging());
        this.canvas?.addEventListener("pointercancel", () => this.stopDragging());
        this.form?.addEventListener("submit", (event) => this.submit(event));
    }

    loadExistingImage() {
        if (!this.preview?.getAttribute("src")) return;

        const image = new Image();
        image.onload = () => this.loadImage(image, "");
        image.onerror = () => {
            if (this.status) {
                this.status.textContent = "เลือกรูปใหม่เพื่อปรับแต่งรูปโปรไฟล์";
            }
        };
        image.src = this.preview.src;
    }

    selectImage() {
        const file = this.input.files?.[0];
        if (!file) return;
        const allowedTypes = ["image/jpeg", "image/png", "image/webp"];
        if (!allowedTypes.includes(file.type) || file.size > 10 * 1024 * 1024) {
            this.input.value = "";
            if (this.status) {
                this.status.textContent = "ไฟล์ไม่ถูกต้อง กรุณาเลือก JPG, PNG หรือ WebP ขนาดไม่เกิน 10 MB";
            }
            return;
        }

        const selectedUrl = this.previewUrl.create(file);
        const image = new Image();
        image.onload = () => {
            if (selectedUrl === this.previewUrl.value) {
                this.loadImage(image, "selected");
            }
        };
        image.onerror = () => {
            if (selectedUrl !== this.previewUrl.value) return;
            this.input.value = "";
            if (this.status) {
                this.status.textContent = "เปิดไฟล์นี้ไม่ได้ กรุณาเลือกรูปอื่น";
            }
        };
        image.src = selectedUrl;
    }

    loadImage(image, source) {
        this.image = image;
        this.imageScale = Math.max(
            this.canvas.width / image.naturalWidth,
            this.canvas.height / image.naturalHeight,
        );
        this.imageCenter = {
            x: this.canvas.width / 2,
            y: this.canvas.height / 2,
        };
        this.zoomInput.value = "1";
        this.cropper.hidden = false;
        this.draw();
        if (this.status) {
            this.status.textContent = source
                ? "รูปพร้อมแล้ว เลื่อนแถบซูมและลากรูปเพื่อจัดตำแหน่ง"
                : "กำลังแสดงรูปโปรไฟล์ปัจจุบัน";
        }
    }

    draw() {
        if (!this.image || !this.canvas || !this.zoomInput) return;
        const context = this.canvas.getContext("2d");
        if (!context) return;

        const size = this.canvas.width;
        const zoom = Number(this.zoomInput.value);
        const width = this.image.naturalWidth * this.imageScale * zoom;
        const height = this.image.naturalHeight * this.imageScale * zoom;
        this.imageCenter.x = Math.max(
            size - width / 2,
            Math.min(width / 2, this.imageCenter.x),
        );
        this.imageCenter.y = Math.max(
            size - height / 2,
            Math.min(height / 2, this.imageCenter.y),
        );

        context.clearRect(0, 0, size, size);
        context.drawImage(
            this.image,
            this.imageCenter.x - width / 2,
            this.imageCenter.y - height / 2,
            width,
            height,
        );
    }

    moveImage(event) {
        if (!this.dragging || !this.pointer) return;
        const bounds = this.canvas.getBoundingClientRect();
        this.imageCenter.x += (event.clientX - this.pointer.x)
            * this.canvas.width / bounds.width;
        this.imageCenter.y += (event.clientY - this.pointer.y)
            * this.canvas.height / bounds.height;
        this.pointer = { x: event.clientX, y: event.clientY };
        this.draw();
    }

    stopDragging() {
        this.dragging = false;
        this.pointer = null;
    }

    submit(event) {
        if (!this.image || !this.input || !this.canvas) return;
        event.preventDefault();

        const outputCanvas = document.createElement("canvas");
        outputCanvas.width = 512;
        outputCanvas.height = 512;
        const context = outputCanvas.getContext("2d");
        if (!context) {
            window.alert("ไม่สามารถเตรียมรูปโปรไฟล์ได้ กรุณาลองอีกครั้ง");
            return;
        }

        const scale = outputCanvas.width / this.canvas.width;
        context.drawImage(
            this.image,
            (this.imageCenter.x - this.canvas.width / 2) * scale,
            (this.imageCenter.y - this.canvas.height / 2) * scale,
            this.image.naturalWidth * this.imageScale
                * Number(this.zoomInput.value) * scale,
            this.image.naturalHeight * this.imageScale
                * Number(this.zoomInput.value) * scale,
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
            this.input.files = transfer.files;
            this.form.submit();
        }, "image/webp", 0.92);
    }
}

class PostMediaPreviewController {
    constructor() {
        this.imageInput = document.querySelector("[data-image-input]");
        this.imagePreview = document.querySelector("[data-image-preview]");
        this.videoInput = document.querySelector("[data-video-input]");
        this.videoPreview = document.querySelector("[data-video-preview]");
        this.imageUrl = new ObjectUrlStore();
        this.videoUrl = new ObjectUrlStore();

        this.imageInput?.addEventListener("change", () => this.previewImage());
        this.videoInput?.addEventListener("change", () => this.previewVideo());
        document.querySelector(
            "[data-image-preview] [data-action='remove-image']",
        )?.addEventListener("click", () => this.removeImage());
    }

    previewImage() {
        const file = this.imageInput.files?.[0];
        if (!file || !this.imagePreview) return;
        if (!file.type.startsWith("image/") || file.size > 10 * 1024 * 1024) {
            this.imageInput.value = "";
            this.imagePreview.hidden = true;
            window.alert("กรุณาเลือกไฟล์รูปภาพขนาดไม่เกิน 10 MB");
            return;
        }

        this.imagePreview.querySelector("img").src = this.imageUrl.create(file);
        this.imagePreview.hidden = false;
    }

    previewVideo() {
        const file = this.videoInput.files?.[0];
        if (!file || !this.videoPreview) return;
        if (!file.type.startsWith("video/") || file.size > 100 * 1024 * 1024) {
            this.videoInput.value = "";
            window.alert("กรุณาเลือกไฟล์วิดีโอขนาดไม่เกิน 100 MB");
            return;
        }

        this.videoPreview.src = this.videoUrl.create(file);
        this.videoPreview.hidden = false;
        this.videoPreview.onloadedmetadata = () => {
            if (this.videoPreview.duration <= 180) return;
            this.videoInput.value = "";
            this.videoPreview.removeAttribute("src");
            this.videoPreview.hidden = true;
            this.videoUrl.clear();
            window.alert("วิดีโอต้องมีความยาวไม่เกิน 3 นาที");
        };
    }

    removeImage() {
        this.imageUrl.clear();
        if (this.imageInput) this.imageInput.value = "";
        if (this.imagePreview) this.imagePreview.hidden = true;
    }
}

class CommunityCoverPreviewController {
    constructor() {
        this.previewUrls = new WeakMap();
        document.querySelectorAll("[data-community-cover-input]").forEach((input) => {
            input.addEventListener("change", () => this.preview(input));
        });
    }

    preview(input) {
        const file = input.files?.[0];
        if (!file) return;

        const preview = input.form.querySelector("[data-community-cover-preview]");
        if (!preview) return;

        this.previewUrls.get(input)?.clear();
        const previewUrl = new ObjectUrlStore();
        this.previewUrls.set(input, previewUrl);
        preview.src = previewUrl.create(file);
        preview.style.display = "block";

        const placeholder = input.form.querySelector(
            "[data-community-cover-placeholder]",
        );
        if (placeholder) placeholder.style.display = "none";
    }
}

new SiteMessageController();
new InlineActionController();
new ProfileCoverController();
new ProfileImageCropController();
new PostMediaPreviewController();
new CommunityCoverPreviewController();
