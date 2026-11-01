/* TSMA performance UI: hide/disable the menu bar and its accelerator groups.
 * Loaded only into slgui through GTK_MODULES. No audio/MIDI interception. */
#include <string.h>
typedef unsigned long GType;
typedef int gboolean;
typedef struct List {void *data;struct List *next,*prev;} List;
extern GType gtk_menu_bar_get_type(void);
extern GType gtk_container_get_type(void);
extern int g_type_check_instance_is_a(void*,GType);
extern List *gtk_container_get_children(void*);
extern List *gtk_window_list_toplevels(void);
extern List *gtk_accel_groups_from_object(void*);
extern void gtk_window_remove_accel_group(void*,void*);
extern void gtk_widget_hide(void*);
extern void gtk_widget_set_sensitive(void*,int);
extern void gtk_widget_set_no_show_all(void*,int);
extern void g_list_free(List*);
extern unsigned int g_timeout_add(unsigned int,gboolean(*)(void*),void*);
extern int gtk_widget_get_visible(void*);
extern int gtk_widget_get_allocated_height(void*);
extern int gtk_widget_translate_coordinates(void*,void*,int,int,int*,int*);
extern const char *gtk_window_get_title(void*);
typedef struct {
 int min_width,min_height,max_width,max_height,base_width,base_height,width_inc,height_inc;
 double min_aspect,max_aspect;int win_gravity;
} Geometry;
extern void gtk_window_set_geometry_hints(void*,void*,Geometry*,int);
/* wxGTK retains the original scroller/menu minimum after the menu disappears.
 * Measure visible leaf controls instead of reserving that obsolete blank area. */
static int control_bottom(void *widget,void *window){
 if(!gtk_widget_get_visible(widget))return 0;
 List *children=NULL;
 if(g_type_check_instance_is_a(widget,gtk_container_get_type()))children=gtk_container_get_children(widget);
 int bottom=0;
 if(children){
  for(List *it=children;it;it=it->next){int edge=control_bottom(it->data,window);if(edge>bottom)bottom=edge;}
  g_list_free(children);
 }else{
  int x,y;
  if(gtk_widget_translate_coordinates(widget,window,0,0,&x,&y))bottom=y+gtk_widget_get_allocated_height(widget);
 }
 return bottom;
}
static void compact(void *window){
 static void *last_window;static int last_height;
 const char *title=gtk_window_get_title(window);
 if(!title||strncmp(title,"SooperLooper v ",14))return;
 int bottom=control_bottom(window,window);
 if(bottom<100)return; /* Wait until wxGTK has allocated the real controls. */
 int height=bottom+4;
 if(window==last_window&&height==last_height)return;
 Geometry geometry={0};geometry.min_width=850;geometry.min_height=height;
 gtk_window_set_geometry_hints(window,NULL,&geometry,1<<1); /* GDK_HINT_MIN_SIZE */
 last_window=window;last_height=height;
}
static void visit(void *widget){
 if(g_type_check_instance_is_a(widget,gtk_menu_bar_get_type())){
  gtk_widget_set_sensitive(widget,0);gtk_widget_set_no_show_all(widget,1);gtk_widget_hide(widget);return;
 }
 if(g_type_check_instance_is_a(widget,gtk_container_get_type())){
  List *children=gtk_container_get_children(widget);
  for(List *it=children;it;it=it->next)visit(it->data);
  g_list_free(children);
 }
}
static gboolean protect(void *unused){
 (void)unused;List *windows=gtk_window_list_toplevels();
 for(List *it=windows;it;it=it->next){
  void *window=it->data;visit(window);compact(window);
  /* Removing groups can mutate the borrowed list, always start again. */
  List *groups;
  while((groups=gtk_accel_groups_from_object(window)))gtk_window_remove_accel_group(window,groups->data);
 }
 g_list_free(windows);return 1;
}
void gtk_module_init(int *argc,char ***argv){(void)argc;(void)argv;g_timeout_add(100,protect,0);}
