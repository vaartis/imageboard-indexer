let vm = new Vue({
    el: "div#all",
    data: {
        images: [],
        displayWholeImages: false
    },

    methods: {
        selectImageDisplayLink: function(image) {
            if (_.has(image, 'metadataOnly')) {
                return this.displayWholeImages ? image.originalImage : image.originalThumbnail;
            } else {
                throw "Link deciding for non-metadata-only images is not implemented yet";
            }
        }
    },

    mounted() {
        axios.get("/get_images").then(response => {
            this.images = response.data;
        });
    }
});

window.onload = function() {
    /*
    let es = new EventSource("/new_images");

    es.onmessage = function(e) {
        // console.log(e.data);
    }
    es.onerror = function(e) {
        // console.log(e);
    }
    */
}
