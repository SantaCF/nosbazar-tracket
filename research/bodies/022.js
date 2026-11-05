$(document).ready(function(){
    $(document).on('click', '.tabs .tab:not(.selected)', function() {
        var tabs = $(this).closest('.tabs')
        var tab_old_selected = tabs.find('.selected');
        var tab_new_selected = $(this);

        if (tabs.hasClass('boxes')){
            var ramka = tabs.closest('.ramka');
            var box = $(this).attr('data-box');

            ramka.find('.dane[data-box="'+tab_old_selected.attr('data-box')+'"]').hide();
            ramka.find('.dane[data-box="'+tab_new_selected.attr('data-box')+'"]').show();
        }

        tabs.find('.selected').removeClass('selected');
        $(this).addClass('selected');
    });

    $(document).on('click', '.window-shop-select-tab:not(.selected)', function() {
        var tab_new_selected = $(this);


        var box_windows = $(this).closest('.shop').find('.windows-shop');

        box_windows.children('div').each(function() {
            var show_windows_indexes = $(this).attr('data-indexes').split(',');
            if (show_windows_indexes.includes(tab_new_selected.attr('data-window-index'))){
                $(this).show();
            } else {
                $(this).hide();
            }
        })

        $('.window-shop-select-tab.selected').removeClass('selected');
        $(this).addClass('selected');
    });

    $(document).on('click', '.nt-slot-item.checkable', function() {
        $(this).toggleClass('selected');
    });

    $(document).on("click", '.nt-popup:not(.nt-popup-prevent-outside-hide)', function(e){
        if(e.target != this) return;
        $(this).hide();
    });

    $(document).on('click', '.popup_close', function(){
        $(this).closest('.nt-popup').hide();
    });
});

$(document).on('mouseenter', '.hover-show-name', function() {
    var attr = $(this).attr('data-name');
    if (typeof attr !== 'undefined' && attr !== false) {
        if (attr.includes("X_PLUS_X")){
            if (typeof $(this).attr('data-plus') !== 'undefined' && Number($(this).attr('data-plus')) > 0){
                attr = attr.replace("X_PLUS_X", " +" + $(this).attr('data-plus'));
            } else {
                attr = attr.replace("X_PLUS_X", "");
            }
        }

        $('#hover-element-name').html(attr);
        setPositionToHoverElement($('#hover-element-name'), $(this));
        $('#hover-element-name').css('visibility', 'visible')
    }
});

$(document).on('mouseleave', '.hover-show-name', function() {
    $('#hover-element-name').css('visibility', 'hidden');
});


function setPositionToHoverElement(element, hover_element){
    var element_width = parseInt(element.outerWidth());
    var element_height = parseInt(element.outerHeight());

    var left = parseInt(hover_element.offset().left) - parseInt($("#divStrona").offset().left);
    var top = parseInt(hover_element.offset().top) - parseInt($("#divStrona").offset().top);

    var position_top = top - element_height;

    var main_end_point = parseInt($("#divStrona").width());

    if (main_end_point < left + element_width){
        element.css('left', '');
        element.css('right', '0');
    } else {
        element.css('left', left);
        element.css('right', '');
    }

    element.css('top', position_top);
}



//minimap zoom
$(document).ready(function(){
    $(document).on('click', '.window-minimap.zoomable', function(){
        if (!$('#zoomed-minimap').length){
            $('body').append('<div id="zoomed-minimap" data-id="-1"></div>');
        }

        if ($(this).attr('data-id') == $('#zoomed-minimap').attr('data-id')){
            $('#zoomed-minimap').show();
        } else {
            $('#zoomed-minimap').attr('data-id', $(this).attr('data-id'));

            var map = $(this).find('.map');
            var zoomed_map_src = map.attr('src').replace('map_previews', 'custom_maps').replace('.png', '.jpg');

            var map_width = map.width() * parseFloat($(this).attr('multipler'));
            var map_height = map.height() * parseFloat($(this).attr('multipler'));
            var map_offset_x = parseFloat($(this).attr('offset-x'));
            var map_offset_y = parseFloat($(this).attr('offset-y'));
            var map_left = parseFloat(map.css('left'));
            var map_top = parseFloat(map.css('top'));
            var zoomed_width = $(this).attr('custom-big-x');
            var zoomed_height = $(this).attr('custom-big-y');
            $('#zoomed-minimap').html('<div id="zoomed-minimap-map" style="width:'+zoomed_width+'px; height:'+zoomed_height+'px"><img src="'+zoomed_map_src+'"/></div>')

            $(this).find('.minimap-point').each(function() {
                var zoomed_left = (parseFloat($(this).css('left')) - map_left - map_offset_x) / map_width * 100;
                var zoomed_top = (parseFloat($(this).css('top')) - map_top - map_offset_y) / map_height * 100;
                var npc_class = $(this).hasClass('minimap-point-npc') ? 'zoomed-map-point-npc' : '';
                $('#zoomed-minimap-map').append('<div class="zoomed-map-point '+ npc_class +'" style="left:'+zoomed_left+'%; top:'+zoomed_top+'%"></div>')
            })

            $('#zoomed-minimap').show();
        }
    });

    $(document).on('click', '#zoomed-minimap', function(){
        $('#zoomed-minimap').hide();
    });
});



var nostale_popup = function () {
    return {
        show_ajax: function (url, post_params) {
            $('body').append('<div id="nostale_popup_wrapper"><div id="nostale_popup"></div></div>')
            $('#nostale_popup_wrapper').css('display', 'flex');
            $('#nostale_popup').html('loading...');


            $.post(url, post_params, function (data) {
                $('#nostale_popup').html(data);
            }, 'html')
        },
        hide: function () {
            $('#nostale_popup_wrapper').remove();
        }
    };
}();

$(document).ready(function (){
    $(document).on("click", '#nostale_popup_wrapper', function(e){
        if(e.target != this) return;
        nostale_popup.hide();
    });
});


function check_if_all_locations_possible(neighbours){
    var unvisited_locations = Object.keys(neighbours).reverse();
    if (unvisited_locations.length){
        var const_start_location = unvisited_locations.pop();

        while (unvisited_locations.length){
            var location = unvisited_locations.shift();
            var path = calculate_shortest_path(const_start_location, location, neighbours);
            if (!path.length){
                return false;
            }
            $.each(path, function (index, remove_location){
                var remove_index = unvisited_locations.indexOf(remove_location);
                if (remove_index !== -1) {
                    unvisited_locations.splice(remove_index, 1);
                }
            })
        }
    }

    return true;
}

function calculate_shortest_path(start, end, neighbours){
    if (!Object.keys(neighbours).length || typeof neighbours[start] === 'undefined' || typeof neighbours[end] === 'undefined'){
        return [];
    }

    let paths = new Map();
    let visited = new Map();
    let distance = new Map();
    for (let [key, value] of Object.entries(neighbours)){
        paths.set(key, [key])
        visited.set(key, false)
        distance.set(key, Infinity)
    }

    distance.set(start, 0)
    let queue = new Queue();
    queue.enqueue(start)
    while(!queue.isEmpty()){
        let current = queue.dequeue();
        visited.set(current, true)

        neighbours[current].forEach(neighbour =>{
            let alt_distance = distance.get(current) + 1

            if(alt_distance < distance.get(neighbour)){
                distance.set(neighbour, alt_distance)
                let path_to_current = JSON.parse(JSON.stringify(paths.get(current)))

                path_to_current.push(neighbour)
                paths.set(neighbour, path_to_current)
            }

            if(visited.get(neighbour) === false){
                queue.enqueue(neighbour)
            }

            if(neighbour === end){
                while(!queue.isEmpty()){
                    queue.dequeue();
                }
            }

        })
    }

    var path = paths.get(end);
    if (path.length > 1){
        return path;
    }

    return [];
}

function Queue(){
    var queue  = [];
    var offset = 0;

    this.getLength = function(){
        return (queue.length - offset);
    }

    this.isEmpty = function(){
        return (queue.length == 0);
    }

    this.enqueue = function(item){
        queue.push(item);
    }

    this.dequeue = function(){
        if (queue.length == 0) return undefined;

        var item = queue[offset];

        if (++ offset * 2 >= queue.length){
            queue  = queue.slice(offset);
            offset = 0;
        }

        return item;
    }

    this.peek = function(){
        return (queue.length > 0 ? queue[offset] : undefined);
    }

}

function getPixelColor(img, x, y, hex = false) {
    var cvs = document.createElement('canvas');

    cvs.width = img.width; cvs.height = img.height
    var ctx = cvs.getContext("2d")
    ctx.drawImage(img,0,0,cvs.width,cvs.height)
    var idt = ctx.getImageData(0,0,cvs.width,cvs.height)

    var i = (y*idt.width+x)*4, d = idt.data

    if (hex){
        if (typeof d[i] === 'undefined'){
            return false;
        }

        var hexString = '';
        hexString += ('00'+d[i].toString(16).toUpperCase()).slice(-2);
        hexString += ('00'+d[i+1].toString(16).toUpperCase()).slice(-2);
        hexString += ('00'+d[i+2].toString(16).toUpperCase()).slice(-2);
        hexString += ('00'+d[i+3].toString(16).toUpperCase()).slice(-2);

        return hexString;
    }

    return [d[i],d[i+1],d[i+2],d[i+3]] // [R,G,B,A]
}

function clearCanvas(canvas) {
    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, canvas.width, canvas.height);
}
function setPixelColor(canvas, x, y, hex, size = 1) {
    const ctx = canvas.getContext("2d");
    ctx.fillStyle = hex || '#000';
    ctx.fillRect(x, y, size, size);
}
