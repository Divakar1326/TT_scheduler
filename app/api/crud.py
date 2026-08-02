"""CRUD REST APIs mapping endpoints to the Repository layer."""
from flask import Blueprint, request, jsonify
from app.repository.entity_repositories import (
    DepartmentRepository, FacultyRepository, CourseRepository,
    SectionRepository, RoomRepository, LabRepository, RulesRepository
)
from app.models.domain import (
    Department, Faculty, Course, Section, Room, Lab, Rule
)
from app.models.mapping import ModelMapper
from app.api.auth import require_role

crud_bp = Blueprint("crud", __name__)

# Repository instantiations
dept_repo = DepartmentRepository()
fac_repo = FacultyRepository()
course_repo = CourseRepository()
sec_repo = SectionRepository()
room_repo = RoomRepository()
lab_repo = LabRepository()
rules_repo = RulesRepository()

# --- Helper helper for standard REST routing ---
from app.repository.entity_repositories import RoomSectionRepository, ClassTeacherRepository
room_sec_repo = RoomSectionRepository()
class_teacher_repo = ClassTeacherRepository()

def section_serializer(sec):
    d = ModelMapper.to_dict(sec)
    rs = room_sec_repo.find_one("room_section", {"section_id": sec.section_id})
    d["classroom"] = rs["room_no"] if rs else ""
    ct = class_teacher_repo.find_one("class_teacher", {"section_id": sec.section_id})
    d["class_teacher"] = ct["faculty_id"] if ct else ""
    return d

def register_crud_routes(bp, repo, model_class, prefix, serializer):
    """Dynamically binds CRUD endpoints for repositories."""
    
    @bp.route(f"/{prefix}", methods=["GET"], endpoint=f"get_all_{prefix}")
    @require_role("HOD")
    def get_all():
        entities = repo.get_all()
        return jsonify([serializer(e) for e in entities])

    @bp.route(f"/{prefix}/<id_val>", methods=["GET"], endpoint=f"get_by_id_{prefix}")
    @require_role("HOD")
    def get_by_id(id_val):
        entity = repo.get_by_id(id_val)
        if not entity:
            return jsonify({"error": "Entity not found"}), 404
        return jsonify(serializer(entity))

    @bp.route(f"/{prefix}", methods=["POST"], endpoint=f"create_{prefix}")
    @require_role("SUPER_ADMIN")
    def create():
        data = request.get_json() or {}
        try:
            # Extract section-specific fields that are not in Section dataclass
            classroom = data.pop("classroom", None) if prefix == "sections" else None
            class_teacher = data.pop("class_teacher", None) if prefix == "sections" else None
            
            entity = model_class(**data)
            created_id = repo.add_entity(entity)
            
            if prefix == "sections":
                room_sec_repo.delete("room_section", {"section_id": entity.section_id})
                class_teacher_repo.delete("class_teacher", {"section_id": entity.section_id})
                if classroom:
                    room_sec_repo.insert("room_section", {"room_no": classroom, "section_id": entity.section_id})
                if class_teacher:
                    class_teacher_repo.insert("class_teacher", {"section_id": entity.section_id, "faculty_id": class_teacher})
                    
            return jsonify({"message": "Created successfully", "id": created_id}), 201
        except Exception as e:
            return jsonify({"error": str(e)}), 400

    @bp.route(f"/{prefix}/<id_val>", methods=["PUT"], endpoint=f"update_{prefix}")
    @require_role("SUPER_ADMIN")
    def update(id_val):
        data = request.get_json() or {}
        try:
            entity = repo.get_by_id(id_val)
            if not entity:
                return jsonify({"error": "Entity not found"}), 404
            
            classroom = data.pop("classroom", None) if prefix == "sections" else None
            class_teacher = data.pop("class_teacher", None) if prefix == "sections" else None
            
            # Reconstruct entity by merging data to trigger dataclass post-init validation
            fields = {f: getattr(entity, f) for f in entity.__dataclass_fields__}
            for k, v in data.items():
                if k in fields:
                    fields[k] = v
                    
            validated_entity = model_class(**fields)
            repo.update_entity(validated_entity)
            
            if prefix == "sections":
                room_sec_repo.delete("room_section", {"section_id": validated_entity.section_id})
                class_teacher_repo.delete("class_teacher", {"section_id": validated_entity.section_id})
                if classroom:
                    room_sec_repo.insert("room_section", {"room_no": classroom, "section_id": validated_entity.section_id})
                if class_teacher:
                    class_teacher_repo.insert("class_teacher", {"section_id": validated_entity.section_id, "faculty_id": class_teacher})
                    
            return jsonify({"message": "Updated successfully"})
        except Exception as e:
            return jsonify({"error": str(e)}), 400

    @bp.route(f"/{prefix}/<id_val>", methods=["DELETE"], endpoint=f"delete_{prefix}")
    @require_role("SUPER_ADMIN")
    def delete(id_val):
        try:
            if prefix == "sections":
                room_sec_repo.delete("room_section", {"section_id": id_val})
                class_teacher_repo.delete("class_teacher", {"section_id": id_val})
            repo.delete_entity(id_val)
            return jsonify({"message": "Deleted successfully"})
        except Exception as e:
            return jsonify({"error": str(e)}), 400

# Bind endpoints
register_crud_routes(crud_bp, dept_repo, Department, "departments", ModelMapper.to_dict)
register_crud_routes(crud_bp, fac_repo, Faculty, "faculties", ModelMapper.to_dict)
register_crud_routes(crud_bp, course_repo, Course, "courses", ModelMapper.to_dict)
register_crud_routes(crud_bp, sec_repo, Section, "sections", section_serializer)
register_crud_routes(crud_bp, room_repo, Room, "rooms", ModelMapper.to_dict)
register_crud_routes(crud_bp, lab_repo, Lab, "laboratories", ModelMapper.to_dict)
register_crud_routes(crud_bp, rules_repo, Rule, "rules", ModelMapper.to_dict)
