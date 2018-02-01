let vm = new Vue({
    el: "div#images-list",
    data: {
        images: []
    },

    mounted() {
        axios.get("/get_images").then(response => {
            this.images = response.data;
        })
    }
});

window.onload = function() {
    let es = new EventSource("/new_images");

    es.onmessage = function(e) {
        // console.log(e.data);
    }
    es.onerror = function(e) {
        // console.log(e);
    }
}
