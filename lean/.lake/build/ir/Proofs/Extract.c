// Lean compiler output
// Module: Proofs.Extract
// Imports: public import Init public meta import Init
#include <lean/lean.h>
#if defined(__clang__)
#pragma clang diagnostic ignored "-Wunused-parameter"
#pragma clang diagnostic ignored "-Wunused-label"
#elif defined(__GNUC__) && !defined(__CLANG__)
#pragma GCC diagnostic ignored "-Wunused-parameter"
#pragma GCC diagnostic ignored "-Wunused-label"
#pragma GCC diagnostic ignored "-Wunused-but-set-variable"
#endif
#ifdef __cplusplus
extern "C" {
#endif
lean_object* l_instDecidableEqString___boxed(lean_object*, lean_object*);
uint8_t lean_string_dec_eq(lean_object*, lean_object*);
lean_object* l_List_appendTR___redArg(lean_object*, lean_object*);
lean_object* lean_array_mk(lean_object*);
lean_object* lean_array_pop(lean_object*);
lean_object* lean_array_to_list(lean_object*);
uint8_t l_List_instDecidableIsPrefixOfDecidableEq___redArg(lean_object*, lean_object*, lean_object*);
static const lean_string_object lp_ghcPythonProofs_GhcPython_resolve___closed__0_value = {.m_header = {.m_rc = 0, .m_cs_sz = 0, .m_other = 0, .m_tag = 249}, .m_size = 2, .m_capacity = 2, .m_length = 1, .m_data = "."};
static const lean_object* lp_ghcPythonProofs_GhcPython_resolve___closed__0 = (const lean_object*)&lp_ghcPythonProofs_GhcPython_resolve___closed__0_value;
static const lean_string_object lp_ghcPythonProofs_GhcPython_resolve___closed__1_value = {.m_header = {.m_rc = 0, .m_cs_sz = 0, .m_other = 0, .m_tag = 249}, .m_size = 3, .m_capacity = 3, .m_length = 2, .m_data = ".."};
static const lean_object* lp_ghcPythonProofs_GhcPython_resolve___closed__1 = (const lean_object*)&lp_ghcPythonProofs_GhcPython_resolve___closed__1_value;
LEAN_EXPORT lean_object* lp_ghcPythonProofs_GhcPython_resolve(lean_object*, lean_object*);
LEAN_EXPORT uint8_t lp_ghcPythonProofs_GhcPython_instDecidableIsWithin(lean_object*, lean_object*);
LEAN_EXPORT lean_object* lp_ghcPythonProofs_GhcPython_instDecidableIsWithin___boxed(lean_object*, lean_object*);
LEAN_EXPORT lean_object* lp_ghcPythonProofs___private_Proofs_Extract_0__GhcPython_resolve_match__1_splitter___redArg(lean_object*, lean_object*, lean_object*, lean_object*);
LEAN_EXPORT lean_object* lp_ghcPythonProofs___private_Proofs_Extract_0__GhcPython_resolve_match__1_splitter(lean_object*, lean_object*, lean_object*, lean_object*, lean_object*);
LEAN_EXPORT lean_object* lp_ghcPythonProofs_GhcPython_resolve(lean_object* v_x_3_, lean_object* v_x_4_){
_start:
{
if (lean_obj_tag(v_x_4_) == 0)
{
return v_x_3_;
}
else
{
lean_object* v_head_5_; lean_object* v_tail_6_; lean_object* v___x_8_; uint8_t v_isShared_9_; uint8_t v_isSharedCheck_25_; 
v_head_5_ = lean_ctor_get(v_x_4_, 0);
v_tail_6_ = lean_ctor_get(v_x_4_, 1);
v_isSharedCheck_25_ = !lean_is_exclusive(v_x_4_);
if (v_isSharedCheck_25_ == 0)
{
v___x_8_ = v_x_4_;
v_isShared_9_ = v_isSharedCheck_25_;
goto v_resetjp_7_;
}
else
{
lean_inc(v_tail_6_);
lean_inc(v_head_5_);
lean_dec(v_x_4_);
v___x_8_ = lean_box(0);
v_isShared_9_ = v_isSharedCheck_25_;
goto v_resetjp_7_;
}
v_resetjp_7_:
{
lean_object* v___x_10_; uint8_t v___x_11_; 
v___x_10_ = ((lean_object*)(lp_ghcPythonProofs_GhcPython_resolve___closed__0));
v___x_11_ = lean_string_dec_eq(v_head_5_, v___x_10_);
if (v___x_11_ == 0)
{
lean_object* v___x_12_; uint8_t v___x_13_; 
v___x_12_ = ((lean_object*)(lp_ghcPythonProofs_GhcPython_resolve___closed__1));
v___x_13_ = lean_string_dec_eq(v_head_5_, v___x_12_);
if (v___x_13_ == 0)
{
lean_object* v___x_14_; lean_object* v___x_16_; 
v___x_14_ = lean_box(0);
if (v_isShared_9_ == 0)
{
lean_ctor_set(v___x_8_, 1, v___x_14_);
v___x_16_ = v___x_8_;
goto v_reusejp_15_;
}
else
{
lean_object* v_reuseFailAlloc_19_; 
v_reuseFailAlloc_19_ = lean_alloc_ctor(1, 2, 0);
lean_ctor_set(v_reuseFailAlloc_19_, 0, v_head_5_);
lean_ctor_set(v_reuseFailAlloc_19_, 1, v___x_14_);
v___x_16_ = v_reuseFailAlloc_19_;
goto v_reusejp_15_;
}
v_reusejp_15_:
{
lean_object* v___x_17_; 
v___x_17_ = l_List_appendTR___redArg(v_x_3_, v___x_16_);
v_x_3_ = v___x_17_;
v_x_4_ = v_tail_6_;
goto _start;
}
}
else
{
lean_object* v___x_20_; lean_object* v___x_21_; lean_object* v___x_22_; 
lean_del_object(v___x_8_);
lean_dec(v_head_5_);
v___x_20_ = lean_array_mk(v_x_3_);
v___x_21_ = lean_array_pop(v___x_20_);
v___x_22_ = lean_array_to_list(v___x_21_);
v_x_3_ = v___x_22_;
v_x_4_ = v_tail_6_;
goto _start;
}
}
else
{
lean_del_object(v___x_8_);
lean_dec(v_head_5_);
v_x_4_ = v_tail_6_;
goto _start;
}
}
}
}
}
LEAN_EXPORT uint8_t lp_ghcPythonProofs_GhcPython_instDecidableIsWithin(lean_object* v_base_26_, lean_object* v_member_27_){
_start:
{
lean_object* v___x_28_; lean_object* v___x_29_; uint8_t v___x_30_; 
v___x_28_ = lean_alloc_closure((void*)(l_instDecidableEqString___boxed), 2, 0);
lean_inc(v_base_26_);
v___x_29_ = lp_ghcPythonProofs_GhcPython_resolve(v_base_26_, v_member_27_);
v___x_30_ = l_List_instDecidableIsPrefixOfDecidableEq___redArg(v___x_28_, v_base_26_, v___x_29_);
return v___x_30_;
}
}
LEAN_EXPORT lean_object* lp_ghcPythonProofs_GhcPython_instDecidableIsWithin___boxed(lean_object* v_base_31_, lean_object* v_member_32_){
_start:
{
uint8_t v_res_33_; lean_object* v_r_34_; 
v_res_33_ = lp_ghcPythonProofs_GhcPython_instDecidableIsWithin(v_base_31_, v_member_32_);
v_r_34_ = lean_box(v_res_33_);
return v_r_34_;
}
}
LEAN_EXPORT lean_object* lp_ghcPythonProofs___private_Proofs_Extract_0__GhcPython_resolve_match__1_splitter___redArg(lean_object* v_x_35_, lean_object* v_x_36_, lean_object* v_h__1_37_, lean_object* v_h__2_38_){
_start:
{
if (lean_obj_tag(v_x_36_) == 0)
{
lean_object* v___x_39_; 
lean_dec(v_h__2_38_);
v___x_39_ = lean_apply_1(v_h__1_37_, v_x_35_);
return v___x_39_;
}
else
{
lean_object* v_head_40_; lean_object* v_tail_41_; lean_object* v___x_42_; 
lean_dec(v_h__1_37_);
v_head_40_ = lean_ctor_get(v_x_36_, 0);
lean_inc(v_head_40_);
v_tail_41_ = lean_ctor_get(v_x_36_, 1);
lean_inc(v_tail_41_);
lean_dec_ref_known(v_x_36_, 2);
v___x_42_ = lean_apply_3(v_h__2_38_, v_x_35_, v_head_40_, v_tail_41_);
return v___x_42_;
}
}
}
LEAN_EXPORT lean_object* lp_ghcPythonProofs___private_Proofs_Extract_0__GhcPython_resolve_match__1_splitter(lean_object* v_motive_43_, lean_object* v_x_44_, lean_object* v_x_45_, lean_object* v_h__1_46_, lean_object* v_h__2_47_){
_start:
{
if (lean_obj_tag(v_x_45_) == 0)
{
lean_object* v___x_48_; 
lean_dec(v_h__2_47_);
v___x_48_ = lean_apply_1(v_h__1_46_, v_x_44_);
return v___x_48_;
}
else
{
lean_object* v_head_49_; lean_object* v_tail_50_; lean_object* v___x_51_; 
lean_dec(v_h__1_46_);
v_head_49_ = lean_ctor_get(v_x_45_, 0);
lean_inc(v_head_49_);
v_tail_50_ = lean_ctor_get(v_x_45_, 1);
lean_inc(v_tail_50_);
lean_dec_ref_known(v_x_45_, 2);
v___x_51_ = lean_apply_3(v_h__2_47_, v_x_44_, v_head_49_, v_tail_50_);
return v___x_51_;
}
}
}
lean_object* initialize_Init(uint8_t builtin);
lean_object* initialize_Init(uint8_t builtin);
static bool _G_initialized = false;
LEAN_EXPORT lean_object* initialize_ghcPythonProofs_Proofs_Extract(uint8_t builtin) {
lean_object * res;
if (_G_initialized) return lean_io_result_mk_ok(lean_box(0));
_G_initialized = true;
res = initialize_Init(builtin);
if (lean_io_result_is_error(res)) return res;
lean_dec_ref(res);
res = initialize_Init(builtin);
if (lean_io_result_is_error(res)) return res;
lean_dec_ref(res);
return lean_io_result_mk_ok(lean_box(0));
}
#ifdef __cplusplus
}
#endif
