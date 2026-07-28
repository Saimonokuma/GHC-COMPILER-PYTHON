// Lean compiler output
// Module: Proofs.Guard
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
uint8_t lean_uint32_dec_eq(uint32_t, uint32_t);
lean_object* l_List_lengthTR___redArg(lean_object*);
lean_object* l_List_drop___redArg(lean_object*, lean_object*);
uint8_t lean_uint32_dec_le(uint32_t, uint32_t);
LEAN_EXPORT uint8_t lp_ghcPythonProofs_List_isPrefixOf___at___00Guard_versionedMatch_spec__0(lean_object*, lean_object*);
LEAN_EXPORT lean_object* lp_ghcPythonProofs_List_isPrefixOf___at___00Guard_versionedMatch_spec__0___boxed(lean_object*, lean_object*);
LEAN_EXPORT uint8_t lp_ghcPythonProofs_Guard_versionedMatch(lean_object*, lean_object*);
LEAN_EXPORT lean_object* lp_ghcPythonProofs_Guard_versionedMatch___boxed(lean_object*, lean_object*);
LEAN_EXPORT uint8_t lp_ghcPythonProofs_Guard_looseMatch(lean_object*, lean_object*);
LEAN_EXPORT lean_object* lp_ghcPythonProofs_Guard_looseMatch___boxed(lean_object*, lean_object*);
LEAN_EXPORT lean_object* lp_ghcPythonProofs___private_Proofs_Guard_0__Guard_versionedMatch_match__1_splitter___redArg___boxed__const__1;
LEAN_EXPORT lean_object* lp_ghcPythonProofs___private_Proofs_Guard_0__Guard_versionedMatch_match__1_splitter___redArg(lean_object*, lean_object*, lean_object*);
LEAN_EXPORT lean_object* lp_ghcPythonProofs___private_Proofs_Guard_0__Guard_versionedMatch_match__1_splitter(lean_object*, lean_object*, lean_object*, lean_object*);
LEAN_EXPORT uint8_t lp_ghcPythonProofs_List_isPrefixOf___at___00Guard_versionedMatch_spec__0(lean_object* v_x_1_, lean_object* v_x_2_){
_start:
{
if (lean_obj_tag(v_x_1_) == 0)
{
uint8_t v___x_3_; 
v___x_3_ = 1;
return v___x_3_;
}
else
{
if (lean_obj_tag(v_x_2_) == 0)
{
uint8_t v___x_4_; 
v___x_4_ = 0;
return v___x_4_;
}
else
{
lean_object* v_head_5_; lean_object* v_tail_6_; lean_object* v_head_7_; lean_object* v_tail_8_; uint32_t v___x_9_; uint32_t v___x_10_; uint8_t v___x_11_; 
v_head_5_ = lean_ctor_get(v_x_1_, 0);
v_tail_6_ = lean_ctor_get(v_x_1_, 1);
v_head_7_ = lean_ctor_get(v_x_2_, 0);
v_tail_8_ = lean_ctor_get(v_x_2_, 1);
v___x_9_ = lean_unbox_uint32(v_head_5_);
v___x_10_ = lean_unbox_uint32(v_head_7_);
v___x_11_ = lean_uint32_dec_eq(v___x_9_, v___x_10_);
if (v___x_11_ == 0)
{
return v___x_11_;
}
else
{
v_x_1_ = v_tail_6_;
v_x_2_ = v_tail_8_;
goto _start;
}
}
}
}
}
LEAN_EXPORT lean_object* lp_ghcPythonProofs_List_isPrefixOf___at___00Guard_versionedMatch_spec__0___boxed(lean_object* v_x_13_, lean_object* v_x_14_){
_start:
{
uint8_t v_res_15_; lean_object* v_r_16_; 
v_res_15_ = lp_ghcPythonProofs_List_isPrefixOf___at___00Guard_versionedMatch_spec__0(v_x_13_, v_x_14_);
lean_dec(v_x_14_);
lean_dec(v_x_13_);
v_r_16_ = lean_box(v_res_15_);
return v_r_16_;
}
}
LEAN_EXPORT uint8_t lp_ghcPythonProofs_Guard_versionedMatch(lean_object* v_tool_17_, lean_object* v_name_18_){
_start:
{
lean_object* v___x_19_; lean_object* v___x_20_; 
v___x_19_ = l_List_lengthTR___redArg(v_tool_17_);
v___x_20_ = l_List_drop___redArg(v___x_19_, v_name_18_);
if (lean_obj_tag(v___x_20_) == 1)
{
lean_object* v_head_21_; lean_object* v_tail_22_; uint32_t v___x_23_; uint32_t v___x_24_; uint8_t v___x_25_; 
v_head_21_ = lean_ctor_get(v___x_20_, 0);
lean_inc(v_head_21_);
v_tail_22_ = lean_ctor_get(v___x_20_, 1);
lean_inc(v_tail_22_);
lean_dec_ref_known(v___x_20_, 2);
v___x_23_ = 45;
v___x_24_ = lean_unbox_uint32(v_head_21_);
lean_dec(v_head_21_);
v___x_25_ = lean_uint32_dec_eq(v___x_24_, v___x_23_);
if (v___x_25_ == 0)
{
lean_dec(v_tail_22_);
return v___x_25_;
}
else
{
if (lean_obj_tag(v_tail_22_) == 1)
{
lean_object* v_head_26_; uint8_t v___x_27_; 
v_head_26_ = lean_ctor_get(v_tail_22_, 0);
lean_inc(v_head_26_);
lean_dec_ref_known(v_tail_22_, 2);
v___x_27_ = lp_ghcPythonProofs_List_isPrefixOf___at___00Guard_versionedMatch_spec__0(v_tool_17_, v_name_18_);
if (v___x_27_ == 0)
{
lean_dec(v_head_26_);
return v___x_27_;
}
else
{
uint32_t v___x_28_; uint32_t v___x_29_; uint8_t v___x_30_; 
v___x_28_ = 48;
v___x_29_ = lean_unbox_uint32(v_head_26_);
v___x_30_ = lean_uint32_dec_le(v___x_28_, v___x_29_);
if (v___x_30_ == 0)
{
lean_dec(v_head_26_);
return v___x_30_;
}
else
{
uint32_t v___x_31_; uint32_t v___x_32_; uint8_t v___x_33_; 
v___x_31_ = 57;
v___x_32_ = lean_unbox_uint32(v_head_26_);
lean_dec(v_head_26_);
v___x_33_ = lean_uint32_dec_le(v___x_32_, v___x_31_);
return v___x_33_;
}
}
}
else
{
uint8_t v___x_34_; 
lean_dec(v_tail_22_);
v___x_34_ = 0;
return v___x_34_;
}
}
}
else
{
uint8_t v___x_35_; 
lean_dec(v___x_20_);
v___x_35_ = 0;
return v___x_35_;
}
}
}
LEAN_EXPORT lean_object* lp_ghcPythonProofs_Guard_versionedMatch___boxed(lean_object* v_tool_36_, lean_object* v_name_37_){
_start:
{
uint8_t v_res_38_; lean_object* v_r_39_; 
v_res_38_ = lp_ghcPythonProofs_Guard_versionedMatch(v_tool_36_, v_name_37_);
lean_dec(v_name_37_);
lean_dec(v_tool_36_);
v_r_39_ = lean_box(v_res_38_);
return v_r_39_;
}
}
LEAN_EXPORT uint8_t lp_ghcPythonProofs_Guard_looseMatch(lean_object* v_tool_40_, lean_object* v_name_41_){
_start:
{
lean_object* v___x_42_; lean_object* v___x_43_; 
v___x_42_ = l_List_lengthTR___redArg(v_tool_40_);
v___x_43_ = l_List_drop___redArg(v___x_42_, v_name_41_);
if (lean_obj_tag(v___x_43_) == 1)
{
lean_object* v_head_44_; lean_object* v_tail_45_; uint32_t v___x_46_; uint32_t v___x_47_; uint8_t v___x_48_; 
v_head_44_ = lean_ctor_get(v___x_43_, 0);
lean_inc(v_head_44_);
v_tail_45_ = lean_ctor_get(v___x_43_, 1);
lean_inc(v_tail_45_);
lean_dec_ref_known(v___x_43_, 2);
v___x_46_ = 45;
v___x_47_ = lean_unbox_uint32(v_head_44_);
lean_dec(v_head_44_);
v___x_48_ = lean_uint32_dec_eq(v___x_47_, v___x_46_);
if (v___x_48_ == 0)
{
lean_dec(v_tail_45_);
return v___x_48_;
}
else
{
if (lean_obj_tag(v_tail_45_) == 1)
{
uint8_t v___x_49_; 
lean_dec_ref_known(v_tail_45_, 2);
v___x_49_ = lp_ghcPythonProofs_List_isPrefixOf___at___00Guard_versionedMatch_spec__0(v_tool_40_, v_name_41_);
return v___x_49_;
}
else
{
uint8_t v___x_50_; 
lean_dec(v_tail_45_);
v___x_50_ = 0;
return v___x_50_;
}
}
}
else
{
uint8_t v___x_51_; 
lean_dec(v___x_43_);
v___x_51_ = 0;
return v___x_51_;
}
}
}
LEAN_EXPORT lean_object* lp_ghcPythonProofs_Guard_looseMatch___boxed(lean_object* v_tool_52_, lean_object* v_name_53_){
_start:
{
uint8_t v_res_54_; lean_object* v_r_55_; 
v_res_54_ = lp_ghcPythonProofs_Guard_looseMatch(v_tool_52_, v_name_53_);
lean_dec(v_name_53_);
lean_dec(v_tool_52_);
v_r_55_ = lean_box(v_res_54_);
return v_r_55_;
}
}
static lean_object* _init_lp_ghcPythonProofs___private_Proofs_Guard_0__Guard_versionedMatch_match__1_splitter___redArg___boxed__const__1(void){
_start:
{
uint32_t v___x_56_; lean_object* v___x_57_; 
v___x_56_ = 45;
v___x_57_ = lean_box_uint32(v___x_56_);
return v___x_57_;
}
}
LEAN_EXPORT lean_object* lp_ghcPythonProofs___private_Proofs_Guard_0__Guard_versionedMatch_match__1_splitter___redArg(lean_object* v_x_58_, lean_object* v_h__1_59_, lean_object* v_h__2_60_){
_start:
{
if (lean_obj_tag(v_x_58_) == 1)
{
lean_object* v_head_61_; lean_object* v_tail_62_; uint32_t v___x_63_; uint32_t v___x_64_; uint8_t v___x_65_; 
v_head_61_ = lean_ctor_get(v_x_58_, 0);
v_tail_62_ = lean_ctor_get(v_x_58_, 1);
v___x_63_ = 45;
v___x_64_ = lean_unbox_uint32(v_head_61_);
v___x_65_ = lean_uint32_dec_eq(v___x_64_, v___x_63_);
if (v___x_65_ == 0)
{
lean_object* v___x_66_; 
lean_dec(v_h__1_59_);
v___x_66_ = lean_apply_2(v_h__2_60_, v_x_58_, lean_box(0));
return v___x_66_;
}
else
{
lean_object* v___x_68_; uint8_t v_isShared_69_; uint8_t v_isSharedCheck_78_; 
lean_inc(v_tail_62_);
v_isSharedCheck_78_ = !lean_is_exclusive(v_x_58_);
if (v_isSharedCheck_78_ == 0)
{
lean_object* v_unused_79_; lean_object* v_unused_80_; 
v_unused_79_ = lean_ctor_get(v_x_58_, 1);
lean_dec(v_unused_79_);
v_unused_80_ = lean_ctor_get(v_x_58_, 0);
lean_dec(v_unused_80_);
v___x_68_ = v_x_58_;
v_isShared_69_ = v_isSharedCheck_78_;
goto v_resetjp_67_;
}
else
{
lean_dec(v_x_58_);
v___x_68_ = lean_box(0);
v_isShared_69_ = v_isSharedCheck_78_;
goto v_resetjp_67_;
}
v_resetjp_67_:
{
if (lean_obj_tag(v_tail_62_) == 1)
{
lean_object* v_head_70_; lean_object* v_tail_71_; lean_object* v___x_72_; 
lean_del_object(v___x_68_);
lean_dec(v_h__2_60_);
v_head_70_ = lean_ctor_get(v_tail_62_, 0);
lean_inc(v_head_70_);
v_tail_71_ = lean_ctor_get(v_tail_62_, 1);
lean_inc(v_tail_71_);
lean_dec_ref_known(v_tail_62_, 2);
v___x_72_ = lean_apply_2(v_h__1_59_, v_head_70_, v_tail_71_);
return v___x_72_;
}
else
{
lean_object* v___x_73_; lean_object* v___x_75_; 
lean_dec(v_h__1_59_);
v___x_73_ = lp_ghcPythonProofs___private_Proofs_Guard_0__Guard_versionedMatch_match__1_splitter___redArg___boxed__const__1;
if (v_isShared_69_ == 0)
{
lean_ctor_set(v___x_68_, 0, v___x_73_);
v___x_75_ = v___x_68_;
goto v_reusejp_74_;
}
else
{
lean_object* v_reuseFailAlloc_77_; 
v_reuseFailAlloc_77_ = lean_alloc_ctor(1, 2, 0);
lean_ctor_set(v_reuseFailAlloc_77_, 0, v___x_73_);
lean_ctor_set(v_reuseFailAlloc_77_, 1, v_tail_62_);
v___x_75_ = v_reuseFailAlloc_77_;
goto v_reusejp_74_;
}
v_reusejp_74_:
{
lean_object* v___x_76_; 
v___x_76_ = lean_apply_2(v_h__2_60_, v___x_75_, lean_box(0));
return v___x_76_;
}
}
}
}
}
else
{
lean_object* v___x_81_; 
lean_dec(v_h__1_59_);
v___x_81_ = lean_apply_2(v_h__2_60_, v_x_58_, lean_box(0));
return v___x_81_;
}
}
}
LEAN_EXPORT lean_object* lp_ghcPythonProofs___private_Proofs_Guard_0__Guard_versionedMatch_match__1_splitter(lean_object* v_motive_82_, lean_object* v_x_83_, lean_object* v_h__1_84_, lean_object* v_h__2_85_){
_start:
{
if (lean_obj_tag(v_x_83_) == 1)
{
lean_object* v_head_86_; lean_object* v_tail_87_; uint32_t v___x_88_; uint32_t v___x_89_; uint8_t v___x_90_; 
v_head_86_ = lean_ctor_get(v_x_83_, 0);
v_tail_87_ = lean_ctor_get(v_x_83_, 1);
v___x_88_ = 45;
v___x_89_ = lean_unbox_uint32(v_head_86_);
v___x_90_ = lean_uint32_dec_eq(v___x_89_, v___x_88_);
if (v___x_90_ == 0)
{
lean_object* v___x_91_; 
lean_dec(v_h__1_84_);
v___x_91_ = lean_apply_2(v_h__2_85_, v_x_83_, lean_box(0));
return v___x_91_;
}
else
{
lean_object* v___x_93_; uint8_t v_isShared_94_; uint8_t v_isSharedCheck_103_; 
lean_inc(v_tail_87_);
v_isSharedCheck_103_ = !lean_is_exclusive(v_x_83_);
if (v_isSharedCheck_103_ == 0)
{
lean_object* v_unused_104_; lean_object* v_unused_105_; 
v_unused_104_ = lean_ctor_get(v_x_83_, 1);
lean_dec(v_unused_104_);
v_unused_105_ = lean_ctor_get(v_x_83_, 0);
lean_dec(v_unused_105_);
v___x_93_ = v_x_83_;
v_isShared_94_ = v_isSharedCheck_103_;
goto v_resetjp_92_;
}
else
{
lean_dec(v_x_83_);
v___x_93_ = lean_box(0);
v_isShared_94_ = v_isSharedCheck_103_;
goto v_resetjp_92_;
}
v_resetjp_92_:
{
if (lean_obj_tag(v_tail_87_) == 1)
{
lean_object* v_head_95_; lean_object* v_tail_96_; lean_object* v___x_97_; 
lean_del_object(v___x_93_);
lean_dec(v_h__2_85_);
v_head_95_ = lean_ctor_get(v_tail_87_, 0);
lean_inc(v_head_95_);
v_tail_96_ = lean_ctor_get(v_tail_87_, 1);
lean_inc(v_tail_96_);
lean_dec_ref_known(v_tail_87_, 2);
v___x_97_ = lean_apply_2(v_h__1_84_, v_head_95_, v_tail_96_);
return v___x_97_;
}
else
{
lean_object* v___x_98_; lean_object* v___x_100_; 
lean_dec(v_h__1_84_);
v___x_98_ = lp_ghcPythonProofs___private_Proofs_Guard_0__Guard_versionedMatch_match__1_splitter___redArg___boxed__const__1;
if (v_isShared_94_ == 0)
{
lean_ctor_set(v___x_93_, 0, v___x_98_);
v___x_100_ = v___x_93_;
goto v_reusejp_99_;
}
else
{
lean_object* v_reuseFailAlloc_102_; 
v_reuseFailAlloc_102_ = lean_alloc_ctor(1, 2, 0);
lean_ctor_set(v_reuseFailAlloc_102_, 0, v___x_98_);
lean_ctor_set(v_reuseFailAlloc_102_, 1, v_tail_87_);
v___x_100_ = v_reuseFailAlloc_102_;
goto v_reusejp_99_;
}
v_reusejp_99_:
{
lean_object* v___x_101_; 
v___x_101_ = lean_apply_2(v_h__2_85_, v___x_100_, lean_box(0));
return v___x_101_;
}
}
}
}
}
else
{
lean_object* v___x_106_; 
lean_dec(v_h__1_84_);
v___x_106_ = lean_apply_2(v_h__2_85_, v_x_83_, lean_box(0));
return v___x_106_;
}
}
}
lean_object* initialize_Init(uint8_t builtin);
lean_object* initialize_Init(uint8_t builtin);
static bool _G_initialized = false;
LEAN_EXPORT lean_object* initialize_ghcPythonProofs_Proofs_Guard(uint8_t builtin) {
lean_object * res;
if (_G_initialized) return lean_io_result_mk_ok(lean_box(0));
_G_initialized = true;
res = initialize_Init(builtin);
if (lean_io_result_is_error(res)) return res;
lean_dec_ref(res);
res = initialize_Init(builtin);
if (lean_io_result_is_error(res)) return res;
lean_dec_ref(res);
lp_ghcPythonProofs___private_Proofs_Guard_0__Guard_versionedMatch_match__1_splitter___redArg___boxed__const__1 = _init_lp_ghcPythonProofs___private_Proofs_Guard_0__Guard_versionedMatch_match__1_splitter___redArg___boxed__const__1();
lean_mark_persistent(lp_ghcPythonProofs___private_Proofs_Guard_0__Guard_versionedMatch_match__1_splitter___redArg___boxed__const__1);
return lean_io_result_mk_ok(lean_box(0));
}
#ifdef __cplusplus
}
#endif
